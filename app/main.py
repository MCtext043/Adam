import json
import os
import secrets
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Generator

from app.admin_auth import clear_admin, is_admin, set_admin
from app.elplat import (
    callback_ip_allowed,
    create_dynamic_qr,
    elplat_config,
    elplat_ready,
    get_payment_status,
    public_base_url,
)
from app.email_service import send_order_email, smtp_ready

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, create_engine, func, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, selectinload, sessionmaker
from starlette.middleware.sessions import SessionMiddleware


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5433/adam_delivery",
)
SESSION_SECRET = (os.getenv("SESSION_SECRET") or "dev-change-me-in-production").strip()
if not SESSION_SECRET:
    SESSION_SECRET = "dev-change-me-in-production"
ADMIN_USERNAME = (os.getenv("ADMIN_USERNAME") or "admin").strip()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD") or "admin"

YANDEX_MAP_ORG_URL = "https://yandex.ru/maps/org/adam/1084526191?si=n4aate9mbpg97k4ecwxfrp3crm"
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI(title="Adam Cafe Delivery")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, https_only=False, same_site="lax")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["yandex_map_org_url"] = YANDEX_MAP_ORG_URL


@app.get("/health")
def health() -> dict:
    with SessionLocal() as session:
        session.execute(text("SELECT 1"))
    return {"status": "ok"}


ORDER_STATUSES = ("pending_payment", "new", "cooking", "delivering", "done", "cancelled")


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    loyalty_points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(40), nullable=False)
    customer_email: Mapped[str] = mapped_column(String(320), default="", nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="new", nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    loyalty_points_earned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    loyalty_points_spent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payment_status: Mapped[str] = mapped_column(String(20), default="none", nullable=False)
    qrc_id: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    elplat_ebl27: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    payment_token: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )
    customer: Mapped[Customer | None] = relationship(back_populates="orders")


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    min_order_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("500.00"))


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    product_name: Mapped[str] = mapped_column(String(120), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()


class CartItemIn(BaseModel):
    product_id: int
    quantity: int = Field(ge=1, le=50)


class OrderCreate(BaseModel):
    customer_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=5, max_length=40)
    email: EmailStr | None = None
    address: str = Field(min_length=8, max_length=500)
    comment: str = Field(default="", max_length=500)
    items: list[CartItemIn] = Field(min_length=1)
    loyalty_points_to_spend: int = Field(default=0, ge=0, le=100_000)

    @field_validator("email", mode="before")
    @classmethod
    def empty_email_to_none(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value


class OrderStatusUpdate(BaseModel):
    status: str


class AdminSettingsUpdate(BaseModel):
    min_order_amount: float = Field(ge=0, le=1_000_000)


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(default="", max_length=40)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


Db = Annotated[Session, Depends(get_db)]


@contextmanager
def startup_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()


def migrate_schema() -> None:
    stmts = [
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_email VARCHAR(320) NOT NULL DEFAULT ''",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS customer_id INTEGER",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS loyalty_points_earned INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS loyalty_points_spent INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE customers ADD COLUMN IF NOT EXISTS loyalty_points INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE products ALTER COLUMN image_url TYPE VARCHAR(500)",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_status VARCHAR(20) NOT NULL DEFAULT 'none'",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS qrc_id VARCHAR(80) NOT NULL DEFAULT ''",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS elplat_ebl27 VARCHAR(80) NOT NULL DEFAULT ''",
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_token VARCHAR(64) NOT NULL DEFAULT ''",
    ]
    with engine.begin() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))
        conn.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.table_constraints
                        WHERE constraint_schema = 'public'
                          AND table_name = 'orders'
                          AND constraint_name = 'orders_customer_id_fkey'
                    ) THEN
                        ALTER TABLE orders
                        ADD CONSTRAINT orders_customer_id_fkey
                        FOREIGN KEY (customer_id) REFERENCES customers(id);
                    END IF;
                END $$;
                """
            )
        )


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    migrate_schema()
    seed_products()
    seed_app_settings()
    if smtp_ready():
        from app.email_service import resolve_sender

        host, user, _, mail_from, port, use_tls = resolve_sender()
        print(f"[smtp] enabled {host}:{port} from={mail_from} user={user} tls={use_tls}")
    else:
        print("[smtp] disabled — set SMTP_HOST and SMTP_USER in .env")
    if elplat_ready():
        print(f"[elplat] enabled {public_base_url()} -> {elplat_config()['api_url']}")
    else:
        print("[elplat] disabled — set ELPLAT_ENABLED=true and credentials in .env")


def gallery_photo_urls() -> list[str]:
    return [
        "https://avatars.mds.yandex.net/get-altay/4581272/2a00000179d7c643dfef942022d32e23c80c/XXL_height",
        "https://avatars.mds.yandex.net/get-altay/10647561/2a0000018c5e80bc2949aad8e044a9809fcc/XXL_height",
        "https://avatars.mds.yandex.net/get-altay/998237/2a0000018741757defbf85e38177a53877d9/XXL_height",
    ]


VK_MENU_PATH = Path(__file__).resolve().parents[1] / "data" / "vk_menu.json"


def _upgrade_vk_image_url(url: str) -> str:
    if "size=0x400" in url:
        return url.replace("size=0x400", "size=604x604")
    return url


def _is_real_vk_product(raw: dict) -> bool:
    vk_id = raw.get("vk_id") or 0
    try:
        price = Decimal(str(raw.get("price") or "0"))
    except Exception:
        return False
    return vk_id > 1_000_000 and price > 0 and bool(raw.get("image_url"))


def load_vk_menu_items() -> list[dict]:
    if not VK_MENU_PATH.is_file():
        return []
    data = json.loads(VK_MENU_PATH.read_text(encoding="utf-8"))
    items = []
    for raw in data:
        if not _is_real_vk_product(raw):
            continue
        items.append(
            {
                "name": raw["name"].strip(),
                "description": (raw.get("description") or raw["name"]).strip()[:2000],
                "price": Decimal(str(raw["price"])),
                "category": (raw.get("category") or "Меню").strip() or "Меню",
                "image_url": _upgrade_vk_image_url(raw["image_url"]),
                "is_active": True,
            }
        )
    return items


def import_vk_products(session: Session) -> int:
    menu_items = load_vk_menu_items()
    if not menu_items:
        return 0

    by_name = {p.name: p for p in session.scalars(select(Product)).all()}
    vk_names = {item["name"] for item in menu_items}
    changed = 0

    for item in menu_items:
        product = by_name.get(item["name"])
        if product is None:
            session.add(Product(**item))
            changed += 1
            continue
        product.description = item["description"]
        product.price = item["price"]
        product.category = item["category"]
        product.image_url = item["image_url"]
        product.is_active = True
        changed += 1

    for product in by_name.values():
        if product.name not in vk_names and product.is_active:
            product.is_active = False
            changed += 1

    return changed


def seed_products() -> None:
    vk_items = load_vk_menu_items()
    if vk_items:
        with startup_session() as session:
            count = import_vk_products(session)
        print(f"[vk-menu] synced {len(vk_items)} items ({count} db changes)")
        return

    photos = gallery_photo_urls()
    menu_items = [
        {
            "name": "Шашлык из курицы",
            "description": "Сочный куриный шашлык с легкой пряной корочкой, луком и зеленью.",
            "price": Decimal("420.00"),
            "category": "Горячее",
        },
        {
            "name": "Люля-кебаб",
            "description": "Классический люля из рубленого мяса, приготовленный на мангале.",
            "price": Decimal("520.00"),
            "category": "Горячее",
        },
        {
            "name": "Долма в виноградных листьях",
            "description": "Нежная долма с мясной начинкой, рисом и пряными травами.",
            "price": Decimal("470.00"),
            "category": "Горячее",
        },
        {
            "name": "Овощи на мангале",
            "description": "Баклажан, перец, томаты и шампиньоны с ароматом углей.",
            "price": Decimal("360.00"),
            "category": "Горячее",
        },
        {
            "name": "Адам сет",
            "description": "Большое ассорти для компании: шашлык, люля, овощи гриль и соусы.",
            "price": Decimal("1850.00"),
            "category": "Сеты",
        },
        {
            "name": "Семейный сет",
            "description": "Горячие блюда, салат, выпечка и напитки для семейного ужина.",
            "price": Decimal("2450.00"),
            "category": "Сеты",
        },
        {
            "name": "Сет к чаю",
            "description": "Сладкая выпечка, пахлава и домашний чай для уютного вечера.",
            "price": Decimal("980.00"),
            "category": "Сеты",
        },
        {
            "name": "Хачапури по-аджарски",
            "description": "Лодка с сыром сулугуни, сливочным маслом и желтком.",
            "price": Decimal("460.00"),
            "category": "Выпечка",
        },
        {
            "name": "Кутабы с зеленью",
            "description": "Тонкие лепешки с зеленью и сыром, подаются со сливочным маслом.",
            "price": Decimal("310.00"),
            "category": "Выпечка",
        },
        {
            "name": "Лаваш из тандыра",
            "description": "Свежий горячий лаваш к шашлыку, салатам и соусам.",
            "price": Decimal("90.00"),
            "category": "Выпечка",
        },
        {
            "name": "Салат с гранатом",
            "description": "Свежие овощи, зелень, гранат и фирменная заправка кафе «Адам».",
            "price": Decimal("390.00"),
            "category": "Салаты",
        },
        {
            "name": "Греческий салат",
            "description": "Овощи, сыр, маслины и оливковое масло в классическом сочетании.",
            "price": Decimal("360.00"),
            "category": "Салаты",
        },
        {
            "name": "Салат Адам",
            "description": "Курица, свежие овощи, зелень и легкий ореховый соус.",
            "price": Decimal("430.00"),
            "category": "Салаты",
        },
        {
            "name": "Домашний морс",
            "description": "Охлажденный ягодный морс собственного приготовления.",
            "price": Decimal("180.00"),
            "category": "Напитки",
        },
        {
            "name": "Айран",
            "description": "Кисломолочный напиток, который отлично подходит к блюдам на мангале.",
            "price": Decimal("160.00"),
            "category": "Напитки",
        },
        {
            "name": "Чай с чабрецом",
            "description": "Ароматный черный чай с чабрецом и восточными сладостями.",
            "price": Decimal("220.00"),
            "category": "Напитки",
        },
    ]
    for i, item in enumerate(menu_items):
        item["image_url"] = photos[i % len(photos)]
    with startup_session() as session:
        existing_names = set(session.scalars(select(Product.name)).all())
        session.add_all([Product(**item) for item in menu_items if item["name"] not in existing_names])


def seed_app_settings() -> None:
    with startup_session() as session:
        if session.get(AppSettings, 1) is None:
            session.add(AppSettings(id=1, min_order_amount=Decimal("500.00")))


def get_app_settings(db: Session) -> AppSettings:
    settings = db.get(AppSettings, 1)
    if settings is None:
        settings = AppSettings(id=1, min_order_amount=Decimal("500.00"))
        db.add(settings)
        db.flush()
    return settings


def normalize_phone(phone: str) -> str:
    return "".join(char for char in phone.strip() if char.isdigit() or char == "+")


def _safe_compare_str(provided: str, expected: str) -> bool:
    a = provided.strip()
    b = expected.strip()
    if len(a) != len(b):
        return False
    return secrets.compare_digest(a, b)


def verify_admin(username: str, password: str) -> bool:
    return _safe_compare_str(username, ADMIN_USERNAME) and _safe_compare_str(password, ADMIN_PASSWORD)


def require_admin(request: Request) -> None:
    if not is_admin(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется вход администратора")


def loyalty_points_for_total(total: Decimal) -> int:
    if total <= 0:
        return 0
    return max(1, int(total * Decimal("0.03")))


@app.get("/", response_class=HTMLResponse)
def storefront_home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/menu")
def storefront_menu() -> RedirectResponse:
    return RedirectResponse(url="/#menu", status_code=302)


@app.get("/cart", response_class=HTMLResponse)
def storefront_cart(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "cart.html", {})


@app.get("/checkout", response_class=HTMLResponse)
def storefront_checkout(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "checkout.html", {})


@app.get("/pay/{order_id}", response_class=HTMLResponse)
def payment_page(request: Request, order_id: int, t: str = "") -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "pay.html",
        {"order_id": order_id, "payment_token": t, "elplat_enabled": elplat_ready()},
    )


@app.get("/login", response_class=HTMLResponse)
def page_login(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "login.html", {})


@app.get("/register", response_class=HTMLResponse)
def page_register(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "register.html", {})


@app.get("/account", response_class=HTMLResponse)
def page_account(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "account.html", {})


@app.get("/about", response_class=HTMLResponse)
def page_about(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "about.html", {})


@app.get("/api/store/settings")
def store_settings(db: Db) -> dict:
    settings = get_app_settings(db)
    return {
        "min_order_amount": float(settings.min_order_amount),
        "payment_enabled": elplat_ready(),
    }


@app.get("/admin/login", response_model=None)
def admin_login_page(request: Request) -> HTMLResponse:
    if is_admin(request):
        return RedirectResponse("/admin", status_code=302)
    return templates.TemplateResponse(request, "admin_login.html", {"error": None})


@app.post("/admin/login", response_model=None)
def admin_login_submit(
    request: Request,
    username: str = Form(),
    password: str = Form(),
) -> RedirectResponse | HTMLResponse:
    if not verify_admin(username, password):
        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {"error": "Неверный логин или пароль"},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    try:
        response = RedirectResponse(url="/admin", status_code=302)
        set_admin(response)
        return response
    except Exception as exc:
        print(f"[admin] login cookie failed: {exc}")
        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {"error": "Ошибка входа на сервере. Проверьте SESSION_SECRET в .env и перезапустите приложение."},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@app.get("/admin/logout")
def admin_logout(request: Request) -> RedirectResponse:
    request.session.pop("admin", None)
    response = RedirectResponse(url="/admin/login", status_code=302)
    clear_admin(response)
    return response


@app.get("/admin", response_model=None)
def admin_panel(request: Request) -> HTMLResponse | RedirectResponse:
    if not is_admin(request):
        return RedirectResponse(url="/admin/login", status_code=302)
    return templates.TemplateResponse(request, "admin.html", {"statuses": ORDER_STATUSES})


@app.get("/api/admin/settings")
def admin_get_settings(request: Request, db: Db) -> dict:
    require_admin(request)
    settings = get_app_settings(db)
    return {"min_order_amount": float(settings.min_order_amount)}


@app.patch("/api/admin/settings")
def admin_update_settings(payload: AdminSettingsUpdate, request: Request, db: Db) -> dict:
    require_admin(request)
    settings = get_app_settings(db)
    settings.min_order_amount = Decimal(str(payload.min_order_amount))
    db.commit()
    db.refresh(settings)
    return {"min_order_amount": float(settings.min_order_amount)}


@app.get("/api/products")
def list_products(db: Db) -> list[dict]:
    products = db.scalars(select(Product).where(Product.is_active.is_(True)).order_by(Product.category, Product.id)).all()
    return [
        {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "price": float(product.price),
            "category": product.category,
            "image_url": product.image_url,
        }
        for product in products
    ]


@app.get("/api/auth/me")
def auth_me(request: Request, db: Db) -> dict:
    cid = request.session.get("customer_id")
    if not cid:
        return {"authenticated": False}
    customer = db.get(Customer, cid)
    if customer is None:
        request.session.pop("customer_id", None)
        return {"authenticated": False}
    return {
        "authenticated": True,
        "email": customer.email,
        "name": customer.display_name,
        "phone": customer.phone,
        "loyalty_points": customer.loyalty_points,
    }


@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def auth_register(payload: RegisterIn, db: Db) -> dict:
    email = payload.email.lower().strip()
    if db.scalars(select(Customer).where(Customer.email == email)).first():
        raise HTTPException(status_code=400, detail="Пользователь с таким email уже есть")
    customer = Customer(
        email=email,
        password_hash=pwd_context.hash(payload.password),
        display_name=payload.display_name.strip(),
        phone=normalize_phone(payload.phone) if payload.phone else "",
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return {"ok": True, "email": customer.email}


@app.post("/api/auth/login")
def auth_login(payload: LoginIn, request: Request, db: Db) -> dict:
    email = payload.email.lower().strip()
    customer = db.scalars(select(Customer).where(Customer.email == email)).first()
    if customer is None or not pwd_context.verify(payload.password, customer.password_hash):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    request.session["customer_id"] = customer.id
    return {
        "ok": True,
        "email": customer.email,
        "name": customer.display_name,
        "loyalty_points": customer.loyalty_points,
    }


@app.post("/api/auth/logout")
def auth_logout(request: Request) -> dict:
    request.session.pop("customer_id", None)
    return {"ok": True}


@app.post("/api/orders", status_code=status.HTTP_201_CREATED)
def create_order(payload: OrderCreate, request: Request, db: Db) -> dict:
    product_ids = [item.product_id for item in payload.items]
    products = db.scalars(select(Product).where(Product.id.in_(product_ids), Product.is_active.is_(True))).all()
    products_by_id = {product.id: product for product in products}

    order_items: list[OrderItem] = []
    total = Decimal("0.00")

    for item in payload.items:
        product = products_by_id.get(item.product_id)
        if product is None:
            raise HTTPException(status_code=404, detail=f"Товар #{item.product_id} не найден")

        line_total = product.price * item.quantity
        total += line_total
        order_items.append(
            OrderItem(
                product_id=product.id,
                product_name=product.name,
                quantity=item.quantity,
                price=product.price,
            )
        )

    session_customer_id: int | None = request.session.get("customer_id")
    customer: Customer | None = None
    if session_customer_id is not None:
        customer = db.get(Customer, session_customer_id)

    email_for_order = ""
    if payload.email:
        email_for_order = str(payload.email).strip()
    elif customer is not None:
        email_for_order = customer.email

    if smtp_ready() and not email_for_order:
        raise HTTPException(
            status_code=400,
            detail="Укажите email — на него отправим подтверждение заказа.",
        )

    settings = get_app_settings(db)
    min_order = settings.min_order_amount
    if total < min_order:
        raise HTTPException(
            status_code=400,
            detail=f"Минимальная сумма заказа для доставки — {int(min_order)} ₽. Сейчас в корзине {int(total)} ₽.",
        )

    points_to_spend = payload.loyalty_points_to_spend
    if points_to_spend > 0:
        if customer is None:
            raise HTTPException(status_code=400, detail="Войдите в аккаунт, чтобы списать бонусы")
        if points_to_spend > customer.loyalty_points:
            raise HTTPException(status_code=400, detail="Недостаточно бонусов на счёте")
        max_discount = int(total)
        if points_to_spend > max_discount:
            points_to_spend = max_discount

    final_total = total - Decimal(points_to_spend)
    if final_total < 0:
        final_total = Decimal("0.00")

    loyalty_earned = 0
    if customer is not None:
        loyalty_earned = loyalty_points_for_total(final_total)

    needs_payment = elplat_ready() and final_total > 0
    order = Order(
        customer_name=payload.customer_name.strip(),
        phone=normalize_phone(payload.phone),
        customer_email=email_for_order,
        address=payload.address.strip(),
        comment=payload.comment.strip(),
        total=final_total,
        items=order_items,
        customer_id=customer.id if customer else None,
        loyalty_points_earned=loyalty_earned,
        loyalty_points_spent=points_to_spend,
        status="pending_payment" if needs_payment else "new",
        payment_status="pending" if needs_payment else "none",
        payment_token=secrets.token_urlsafe(24) if needs_payment else "",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    if customer is not None and not needs_payment:
        if points_to_spend > 0:
            customer.loyalty_points -= points_to_spend
        if loyalty_earned > 0:
            customer.loyalty_points += loyalty_earned
        db.commit()

    order = db.scalars(select(Order).options(selectinload(Order.items)).where(Order.id == order.id)).one()

    if not needs_payment:
        try:
            send_order_email(order, kind="created")
        except Exception as exc:
            print(f"[order] email after create failed for #{order.id}: {exc}")

    result = {
        "id": order.id,
        "status": order.status,
        "total": float(order.total),
        "subtotal": float(total),
        "loyalty_points_earned": loyalty_earned if not needs_payment else 0,
        "loyalty_points_spent": points_to_spend,
        "payment_required": needs_payment,
    }
    if needs_payment:
        result["payment_url"] = f"/pay/{order.id}?t={order.payment_token}"
    return result


def get_order_by_payment_token(db: Session, order_id: int, token: str) -> Order:
    order = db.scalars(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    ).first()
    if order is None or not order.payment_token or not secrets.compare_digest(order.payment_token, token):
        raise HTTPException(status_code=404, detail="Заказ не найден")
    return order


def finalize_paid_order(db: Session, order: Order, *, ebl27: str = "", qrc_id: str = "") -> Order:
    if order.payment_status == "paid":
        return order

    order.payment_status = "paid"
    order.status = "new"
    if ebl27:
        order.elplat_ebl27 = ebl27
    if qrc_id:
        order.qrc_id = qrc_id

    customer = db.get(Customer, order.customer_id) if order.customer_id else None
    if customer is not None:
        if order.loyalty_points_spent > 0:
            customer.loyalty_points -= order.loyalty_points_spent
        if order.loyalty_points_earned > 0:
            customer.loyalty_points += order.loyalty_points_earned

    db.commit()
    order = db.scalars(select(Order).options(selectinload(Order.items)).where(Order.id == order.id)).one()
    try:
        send_order_email(order, kind="created")
    except Exception as exc:
        print(f"[order] email after payment failed for #{order.id}: {exc}")
    return order


@app.get("/api/orders/{order_id}/payment/info")
def order_payment_info(order_id: int, db: Db, token: str = Query()) -> dict:
    order = get_order_by_payment_token(db, order_id, token)
    return {
        "order_id": order.id,
        "total": float(order.total),
        "payment_status": order.payment_status,
        "customer_name": order.customer_name,
    }


@app.post("/api/orders/{order_id}/payment/qr")
async def create_order_payment_qr(order_id: int, db: Db, token: str = Query()) -> dict:
    order = get_order_by_payment_token(db, order_id, token)
    if order.payment_status == "paid":
        return {"paid": True, "qr_data": ""}

    if not elplat_ready():
        raise HTTPException(status_code=503, detail="Оплата СБП временно недоступна")

    callback_url = f"{public_base_url()}/api/payments/elplat/callback?order_id={order.id}"
    redirect_url = f"{public_base_url()}/pay/{order.id}?t={order.payment_token}&done=1"
    purpose = f"Заказ {order.id} Кафе Адам"
    try:
        info = await create_dynamic_qr(
            amount_rub=order.total,
            payment_purpose=purpose,
            callback_url=callback_url,
            redirect_url=redirect_url,
            email=order.customer_email or "",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    order.qrc_id = info.get("qrcId") or ""
    db.commit()
    return {
        "paid": False,
        "qr_data": info.get("qrData") or "",
        "qrc_id": order.qrc_id,
        "amount": float(order.total),
    }


@app.get("/api/orders/{order_id}/payment/status")
async def order_payment_status(order_id: int, db: Db, token: str = Query()) -> dict:
    order = get_order_by_payment_token(db, order_id, token)
    if order.payment_status == "paid":
        return {"status": "paid", "order_status": order.status}

    if order.qrc_id and elplat_ready():
        try:
            info = await get_payment_status(order.qrc_id)
            if info.get("trxStatus") == "ACWP":
                order = finalize_paid_order(
                    db,
                    order,
                    ebl27=info.get("ebl27") or "",
                    qrc_id=order.qrc_id,
                )
                return {"status": "paid", "order_status": order.status}
        except Exception as exc:
            print(f"[elplat] getPay order #{order_id}: {exc}")

    return {"status": order.payment_status, "order_status": order.status}


@app.post("/api/payments/elplat/callback")
async def elplat_payment_callback(request: Request, order_id: int, db: Db) -> dict:
    client_host = request.client.host if request.client else None
    if not callback_ip_allowed(client_host):
        print(f"[elplat] callback rejected from {client_host}")
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        body = await request.json()
    except Exception:
        body = {}

    if body.get("payStatus") != 1:
        return {"status": True}

    order = db.scalars(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    ).first()
    if order is None:
        return {"status": True}

    callback_amount = body.get("allAmount") or body.get("amount")
    if callback_amount is not None:
        expected_kop = int((order.total * 100).quantize(Decimal("1")))
        try:
            if int(callback_amount) != expected_kop:
                print(f"[elplat] amount mismatch order #{order_id}: {callback_amount} vs {expected_kop}")
                return {"status": True}
        except (TypeError, ValueError):
            pass

    finalize_paid_order(
        db,
        order,
        ebl27=str(body.get("ebl27") or ""),
        qrc_id=str(body.get("qrcId") or ""),
    )
    return {"status": True}


@app.get("/api/admin/orders")
def list_orders(request: Request, db: Db) -> list[dict]:
    require_admin(request)
    orders = (
        db.scalars(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.status != "done")
            .order_by(Order.id.desc())
        )
        .unique()
        .all()
    )
    return [serialize_order(order) for order in orders]


@app.patch("/api/admin/orders/{order_id}/status")
def update_order_status(order_id: int, payload: OrderStatusUpdate, request: Request, db: Db) -> dict:
    require_admin(request)
    if payload.status not in ORDER_STATUSES:
        raise HTTPException(status_code=400, detail="Неизвестный статус заказа")

    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    order.status = payload.status
    db.commit()
    order = db.scalars(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    ).one()
    send_order_email(order, kind="status")
    return serialize_order(order)


def serialize_order(order: Order) -> dict:
    return {
        "id": order.id,
        "customer_name": order.customer_name,
        "phone": order.phone,
        "customer_email": order.customer_email,
        "address": order.address,
        "comment": order.comment,
        "status": order.status,
        "payment_status": order.payment_status,
        "total": float(order.total),
        "loyalty_points_spent": order.loyalty_points_spent,
        "loyalty_points_earned": order.loyalty_points_earned,
        "created_at": str(order.created_at),
        "items": [
            {
                "product_name": item.product_name,
                "quantity": item.quantity,
                "price": float(item.price),
                "sum": float(item.price * item.quantity),
            }
            for item in order.items
        ],
    }
