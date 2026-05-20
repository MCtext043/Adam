import os
import secrets
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Generator

from app.email_service import send_order_email

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
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
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-change-me-in-production")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

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


ORDER_STATUSES = ("new", "cooking", "delivering", "done", "cancelled")


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


def gallery_photo_urls() -> list[str]:
    return [
        "https://avatars.mds.yandex.net/get-altay/4581272/2a00000179d7c643dfef942022d32e23c80c/XXL_height",
        "https://avatars.mds.yandex.net/get-altay/10647561/2a0000018c5e80bc2949aad8e044a9809fcc/XXL_height",
        "https://avatars.mds.yandex.net/get-altay/998237/2a0000018741757defbf85e38177a53877d9/XXL_height",
    ]


def seed_products() -> None:
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


def verify_admin(username: str, password: str) -> bool:
    if not secrets.compare_digest(username.strip(), ADMIN_USERNAME.strip()):
        return False
    return secrets.compare_digest(password, ADMIN_PASSWORD)


def require_admin(request: Request) -> None:
    if not request.session.get("admin"):
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
    return {"min_order_amount": float(settings.min_order_amount)}


@app.get("/admin/login", response_model=None)
def admin_login_page(request: Request) -> HTMLResponse:
    if request.session.get("admin"):
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
    request.session["admin"] = True
    return RedirectResponse(url="/admin", status_code=303)


@app.get("/admin/logout")
def admin_logout(request: Request) -> RedirectResponse:
    request.session.pop("admin", None)
    return RedirectResponse(url="/admin/login", status_code=302)


@app.get("/admin", response_model=None)
def admin_panel(request: Request) -> HTMLResponse | RedirectResponse:
    if not request.session.get("admin"):
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
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    if customer is not None:
        if points_to_spend > 0:
            customer.loyalty_points -= points_to_spend
        if loyalty_earned > 0:
            customer.loyalty_points += loyalty_earned
        db.commit()

    order = db.scalars(select(Order).options(selectinload(Order.items)).where(Order.id == order.id)).one()
    try:
        send_order_email(order, kind="created")
    except Exception as exc:
        print(f"[order] email after create failed for #{order.id}: {exc}")

    return {
        "id": order.id,
        "status": order.status,
        "total": float(order.total),
        "subtotal": float(total),
        "loyalty_points_earned": loyalty_earned,
        "loyalty_points_spent": points_to_spend,
    }


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
