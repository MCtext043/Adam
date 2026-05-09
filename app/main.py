import os
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from typing import Generator

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, selectinload, sessionmaker


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5433/adam_delivery",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

app = FastAPI(title="Adam Cafe Delivery")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

ORDER_STATUSES = ("new", "cooking", "delivering", "done", "cancelled")


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    image_url: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(40), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="new", nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )


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
    address: str = Field(min_length=8, max_length=500)
    comment: str = Field(default="", max_length=500)
    items: list[CartItemIn] = Field(min_length=1)


class OrderStatusUpdate(BaseModel):
    status: str


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


@contextmanager
def startup_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    seed_products()


def seed_products() -> None:
    with startup_session() as session:
        menu_items = [
            {
                "name": "Шашлык из курицы",
                "description": "Сочный куриный шашлык с легкой пряной корочкой, луком и зеленью.",
                "price": Decimal("420.00"),
                "category": "Горячее",
                "image_url": "https://images.unsplash.com/photo-1529193591184-b1d58069ecdd?auto=format&fit=crop&w=900&q=80",
            },
            {
                "name": "Люля-кебаб",
                "description": "Классический люля из рубленого мяса, приготовленный на мангале.",
                "price": Decimal("520.00"),
                "category": "Горячее",
                "image_url": "https://images.unsplash.com/photo-1600891964092-4316c288032e?auto=format&fit=crop&w=900&q=80",
            },
            {
                "name": "Долма в виноградных листьях",
                "description": "Нежная долма с мясной начинкой, рисом и пряными травами.",
                "price": Decimal("470.00"),
                "category": "Горячее",
                "image_url": "https://images.unsplash.com/photo-1590846406792-0adc7f938f1d?auto=format&fit=crop&w=900&q=80",
            },
            {
                "name": "Овощи на мангале",
                "description": "Баклажан, перец, томаты и шампиньоны с ароматом углей.",
                "price": Decimal("360.00"),
                "category": "Горячее",
                "image_url": "https://images.unsplash.com/photo-1543352634-a1c51d9f1fa7?auto=format&fit=crop&w=900&q=80",
            },
            {
                "name": "Адам сет",
                "description": "Большое ассорти для компании: шашлык, люля, овощи гриль и соусы.",
                "price": Decimal("1850.00"),
                "category": "Сеты",
                "image_url": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=900&q=80",
            },
            {
                "name": "Семейный сет",
                "description": "Горячие блюда, салат, выпечка и напитки для семейного ужина.",
                "price": Decimal("2450.00"),
                "category": "Сеты",
                "image_url": "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=900&q=80",
            },
            {
                "name": "Сет к чаю",
                "description": "Сладкая выпечка, пахлава и домашний чай для уютного вечера.",
                "price": Decimal("980.00"),
                "category": "Сеты",
                "image_url": "https://images.unsplash.com/photo-1567521464027-f127ff144326?auto=format&fit=crop&w=900&q=80",
            },
            {
                "name": "Хачапури по-аджарски",
                "description": "Лодочка с сыром сулугуни, сливочным маслом и желтком.",
                "price": Decimal("460.00"),
                "category": "Выпечка",
                "image_url": "https://images.unsplash.com/photo-1619197358186-4a6c52b05b17?auto=format&fit=crop&w=900&q=80",
            },
            {
                "name": "Кутабы с зеленью",
                "description": "Тонкие лепешки с зеленью и сыром, подаются со сливочным маслом.",
                "price": Decimal("310.00"),
                "category": "Выпечка",
                "image_url": "https://images.unsplash.com/photo-1601050690597-df0568f70950?auto=format&fit=crop&w=900&q=80",
            },
            {
                "name": "Лаваш из тандыра",
                "description": "Свежий горячий лаваш к шашлыку, салатам и соусам.",
                "price": Decimal("90.00"),
                "category": "Выпечка",
                "image_url": "https://images.unsplash.com/photo-1586444248902-2f64eddc13df?auto=format&fit=crop&w=900&q=80",
            },
            {
                "name": "Салат с гранатом",
                "description": "Свежие овощи, зелень, гранат и фирменная заправка кафе «Адам».",
                "price": Decimal("390.00"),
                "category": "Салаты",
                "image_url": "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=900&q=80",
            },
            {
                "name": "Греческий салат",
                "description": "Овощи, сыр, маслины и оливковое масло в классическом сочетании.",
                "price": Decimal("360.00"),
                "category": "Салаты",
                "image_url": "https://images.unsplash.com/photo-1540420773420-3366772f4999?auto=format&fit=crop&w=900&q=80",
            },
            {
                "name": "Салат Адам",
                "description": "Курица, свежие овощи, зелень и легкий ореховый соус.",
                "price": Decimal("430.00"),
                "category": "Салаты",
                "image_url": "https://images.unsplash.com/photo-1505253716362-afaea1d3d1af?auto=format&fit=crop&w=900&q=80",
            },
            {
                "name": "Домашний морс",
                "description": "Охлажденный ягодный морс собственного приготовления.",
                "price": Decimal("180.00"),
                "category": "Напитки",
                "image_url": "https://images.unsplash.com/photo-1544145945-f90425340c7e?auto=format&fit=crop&w=900&q=80",
            },
            {
                "name": "Айран",
                "description": "Кисломолочный напиток, который отлично подходит к блюдам на мангале.",
                "price": Decimal("160.00"),
                "category": "Напитки",
                "image_url": "https://images.unsplash.com/photo-1577805947697-89e18249d767?auto=format&fit=crop&w=900&q=80",
            },
            {
                "name": "Чай с чабрецом",
                "description": "Ароматный черный чай с чабрецом и восточными сладостями.",
                "price": Decimal("220.00"),
                "category": "Напитки",
                "image_url": "https://images.unsplash.com/photo-1544787219-7f47ccb76574?auto=format&fit=crop&w=900&q=80",
            },
        ]
        existing_names = set(session.scalars(select(Product.name)).all())
        session.add_all([Product(**item) for item in menu_items if item["name"] not in existing_names])


def normalize_phone(phone: str) -> str:
    return "".join(char for char in phone.strip() if char.isdigit() or char == "+")


@app.get("/", response_class=HTMLResponse)
def storefront(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/admin", response_class=HTMLResponse)
def admin_panel(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("admin.html", {"request": request, "statuses": ORDER_STATUSES})


@app.get("/api/products")
def list_products(db: Session = Depends(get_db)) -> list[dict]:
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


@app.post("/api/orders", status_code=status.HTTP_201_CREATED)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)) -> dict:
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

    order = Order(
        customer_name=payload.customer_name.strip(),
        phone=normalize_phone(payload.phone),
        address=payload.address.strip(),
        comment=payload.comment.strip(),
        total=total,
        items=order_items,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    return {"id": order.id, "status": order.status, "total": float(order.total)}


@app.get("/api/admin/orders")
def list_orders(db: Session = Depends(get_db)) -> list[dict]:
    orders = db.scalars(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.status != "done")
        .order_by(Order.id.desc())
    ).unique().all()
    return [serialize_order(order) for order in orders]


@app.patch("/api/admin/orders/{order_id}/status")
def update_order_status(order_id: int, payload: OrderStatusUpdate, db: Session = Depends(get_db)) -> dict:
    if payload.status not in ORDER_STATUSES:
        raise HTTPException(status_code=400, detail="Неизвестный статус заказа")

    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    order.status = payload.status
    db.commit()
    db.refresh(order)
    return serialize_order(order)


def serialize_order(order: Order) -> dict:
    return {
        "id": order.id,
        "customer_name": order.customer_name,
        "phone": order.phone,
        "address": order.address,
        "comment": order.comment,
        "status": order.status,
        "total": float(order.total),
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
