from datetime import date, datetime, timedelta, time
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, Generic, Literal, TypeVar
import os

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pwdlib import PasswordHash
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from dotenv import load_dotenv
from sqlalchemy import Boolean, Date, DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String, Text, Time, UniqueConstraint, create_engine, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./edu_crm.db")
SECRET_KEY = os.getenv("SECRET_KEY", "development-only-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Role(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    TEACHER = "teacher"
    ACCOUNTANT = "accountant"


class StudentStatus(str, Enum):
    ACTIVE = "active"; PAUSED = "paused"; GRADUATED = "graduated"; ARCHIVED = "archived"


class GroupStatus(str, Enum):
    ACTIVE = "active"; PLANNED = "planned"; COMPLETED = "completed"; ARCHIVED = "archived"


class AttendanceStatus(str, Enum):
    PRESENT = "present"; ABSENT = "absent"; LATE = "late"; EXCUSED = "excused"


class PaymentMethod(str, Enum):
    CASH = "cash"; CARD = "card"; TRANSFER = "transfer"


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(SAEnum(Role), default=Role.MANAGER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Teacher(TimestampMixin, Base):
    __tablename__ = "teachers"
    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    specialty: Mapped[str | None] = mapped_column(String(150), nullable=True)
    hired_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    salary_type: Mapped[str] = mapped_column(String(20), default="fixed")
    salary_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    groups: Mapped[list["Group"]] = relationship(back_populates="teacher")


class Course(TimestampMixin, Base):
    __tablename__ = "courses"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_months: Mapped[int] = mapped_column(Integer, default=1)
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    groups: Mapped[list["Group"]] = relationship(back_populates="course")


class Student(TimestampMixin, Base):
    __tablename__ = "students"
    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(80), index=True)
    last_name: Mapped[str] = mapped_column(String(80), index=True)
    phone: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    additional_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    guardian_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    guardian_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    registered_at: Mapped[date] = mapped_column(Date, default=date.today)
    status: Mapped[StudentStatus] = mapped_column(SAEnum(StudentStatus), default=StudentStatus.ACTIVE)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    enrollments: Mapped[list["GroupStudent"]] = relationship(back_populates="student", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship(back_populates="student")


class Group(TimestampMixin, Base):
    __tablename__ = "groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.id"), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    lesson_days: Mapped[str] = mapped_column(String(100), default="")
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    room: Mapped[str | None] = mapped_column(String(50), nullable=True)
    monthly_fee: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    max_students: Mapped[int] = mapped_column(Integer, default=20)
    status: Mapped[GroupStatus] = mapped_column(SAEnum(GroupStatus), default=GroupStatus.PLANNED)
    course: Mapped[Course] = relationship(back_populates="groups")
    teacher: Mapped[Teacher | None] = relationship(back_populates="groups")
    enrollments: Mapped[list["GroupStudent"]] = relationship(back_populates="group", cascade="all, delete-orphan")


class GroupStudent(Base):
    __tablename__ = "group_students"
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), primary_key=True)
    enrolled_at: Mapped[date] = mapped_column(Date, default=date.today)
    group: Mapped[Group] = relationship(back_populates="enrollments")
    student: Mapped[Student] = relationship(back_populates="enrollments")


class Attendance(TimestampMixin, Base):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("group_id", "student_id", "lesson_date", name="uq_attendance_lesson"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    lesson_date: Mapped[date] = mapped_column(Date, default=date.today)
    status: Mapped[AttendanceStatus] = mapped_column(SAEnum(AttendanceStatus), default=AttendanceStatus.PRESENT)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Schedule(TimestampMixin, Base):
    __tablename__ = "schedules"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.id"), nullable=True)
    lesson_date: Mapped[date] = mapped_column(Date, index=True)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    room: Mapped[str | None] = mapped_column(String(50), nullable=True)


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    payment_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    method: Mapped[PaymentMethod] = mapped_column(SAEnum(PaymentMethod), default=PaymentMethod.CASH)
    period: Mapped[str] = mapped_column(String(20))
    discount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    student: Mapped[Student] = relationship(back_populates="payments")


class Expense(TimestampMixin, Base):
    __tablename__ = "expenses"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    category: Mapped[str] = mapped_column(String(100), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    expense_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()


password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
DB = Annotated[Session, Depends(get_db)]


def token_for(user: User) -> str:
    return jwt.encode({"sub": str(user.id), "role": user.role.value, "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)}, SECRET_KEY, algorithm=ALGORITHM)


def current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DB) -> User:
    try: user_id = int(jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])["sub"])
    except (JWTError, KeyError, ValueError): raise HTTPException(401, "Token yaroqsiz yoki muddati tugagan")
    user = db.get(User, user_id)
    if not user or not user.is_active: raise HTTPException(401, "Foydalanuvchi faol emas")
    return user


def permit(*roles: Role):
    def check(user: Annotated[User, Depends(current_user)]) -> User:
        if user.role not in roles: raise HTTPException(403, "Bu amal uchun ruxsat yo‘q")
        return user
    return check


class ORMModel(BaseModel): model_config = ConfigDict(from_attributes=True)
class Token(BaseModel): access_token: str; token_type: str = "bearer"
class UserIn(BaseModel): full_name: str; email: EmailStr; password: str = Field(min_length=8); role: Role = Role.MANAGER; is_active: bool = True
class UserOut(ORMModel): id: int; full_name: str; email: EmailStr; role: Role; is_active: bool
class TeacherIn(BaseModel): first_name: str; last_name: str; phone: str; email: EmailStr | None = None; specialty: str | None = None; hired_at: date | None = None; salary_type: str = "fixed"; salary_amount: Decimal = 0; is_active: bool = True; note: str | None = None
class TeacherOut(ORMModel): id: int; first_name: str; last_name: str; phone: str; email: str | None; specialty: str | None; is_active: bool
class CourseIn(BaseModel): name: str; description: str | None = None; duration_months: int = Field(default=1, ge=1); price: Decimal = Field(default=0, ge=0); is_active: bool = True
class CourseOut(ORMModel): id: int; name: str; description: str | None; duration_months: int; price: Decimal; is_active: bool
class StudentIn(BaseModel): first_name: str; last_name: str; phone: str; additional_phone: str | None = None; birth_date: date | None = None; gender: str | None = None; address: str | None = None; guardian_name: str | None = None; guardian_phone: str | None = None; registered_at: date = Field(default_factory=date.today); status: StudentStatus = StudentStatus.ACTIVE; note: str | None = None
class StudentOut(ORMModel): id: int; first_name: str; last_name: str; phone: str; status: StudentStatus; guardian_name: str | None; registered_at: date
class GroupIn(BaseModel): name: str; course_id: int; teacher_id: int | None = None; start_date: date | None = None; end_date: date | None = None; lesson_days: str = ""; start_time: time | None = None; end_time: time | None = None; room: str | None = None; monthly_fee: Decimal = Field(default=0, ge=0); max_students: int = Field(default=20, ge=1); status: GroupStatus = GroupStatus.PLANNED
class GroupOut(ORMModel): id: int; name: str; course_id: int; teacher_id: int | None; monthly_fee: Decimal; max_students: int; status: GroupStatus; room: str | None
class EnrollmentIn(BaseModel): student_id: int
class AttendanceIn(BaseModel): group_id: int; student_id: int; lesson_date: date = Field(default_factory=date.today); status: AttendanceStatus; note: str | None = None
class AttendanceOut(ORMModel): id: int; group_id: int; student_id: int; lesson_date: date; status: AttendanceStatus; note: str | None
class ScheduleIn(BaseModel): group_id: int; teacher_id: int | None = None; lesson_date: date; start_time: time; end_time: time; room: str | None = None
class ScheduleOut(ORMModel): id: int; group_id: int; teacher_id: int | None; lesson_date: date; start_time: time; end_time: time; room: str | None
class PaymentIn(BaseModel): student_id: int; group_id: int | None = None; amount: Decimal = Field(gt=0); payment_date: date = Field(default_factory=date.today); method: PaymentMethod = PaymentMethod.CASH; period: str; discount: Decimal = Field(default=0, ge=0); note: str | None = None
class PaymentOut(ORMModel): id: int; student_id: int; group_id: int | None; amount: Decimal; payment_date: date; method: PaymentMethod; period: str; discount: Decimal
class ExpenseIn(BaseModel): name: str; category: str; amount: Decimal = Field(gt=0); expense_date: date = Field(default_factory=date.today); note: str | None = None
class ExpenseOut(ORMModel): id: int; name: str; category: str; amount: Decimal; expense_date: date; note: str | None
T = TypeVar("T")

class Page(BaseModel, Generic[T]):
    """Pagination envelope used by all list endpoints."""
    items: list[T]
    total: int
    page: int
    page_size: int


def entity_or_404(db: Session, cls, entity_id: int):
    obj = db.get(cls, entity_id)
    if not obj: raise HTTPException(404, "Ma’lumot topilmadi")
    return obj


def save(db: Session, obj):
    try: db.add(obj); db.commit(); db.refresh(obj); return obj
    except IntegrityError: db.rollback(); raise HTTPException(409, "Bu ma’lumot allaqachon mavjud yoki bog‘lanish noto‘g‘ri")


app = FastAPI(title="Edu CRM API", version="1.0.0", description="Ta’lim markazini boshqarish REST API")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","), allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/", tags=["Health"], summary="Backend holatini tekshirish")
def root():
    return {"message": "Edu CRM Backend ishlayapti", "docs": "/docs"}

@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if not db.scalar(select(User.id).limit(1)):
            db.add(User(full_name="Super Admin", email="admin@educrm.uz", password_hash=password_hash.hash("Admin123!"), role=Role.SUPER_ADMIN))
            db.commit()

@app.post("/api/auth/login", response_model=Token, tags=["Authentication"], summary="Tizimga kirish")
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DB):
    user = db.scalar(select(User).where(User.email == form.username))
    if not user or not password_hash.verify(form.password, user.password_hash) or not user.is_active: raise HTTPException(401, "Email yoki parol noto‘g‘ri")
    return Token(access_token=token_for(user))

@app.post("/api/auth/refresh", response_model=Token, tags=["Authentication"])
def refresh(user: Annotated[User, Depends(current_user)]): return Token(access_token=token_for(user))
@app.post("/api/auth/logout", tags=["Authentication"])
def logout(user: Annotated[User, Depends(current_user)]): return {"message": "Tizimdan chiqildi"}
@app.get("/api/auth/me", response_model=UserOut, tags=["Authentication"])
def me(user: Annotated[User, Depends(current_user)]): return user

def paged(stmt, db, page, page_size):
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    return {"items": db.scalars(stmt.offset((page-1)*page_size).limit(page_size)).all(), "total": total, "page": page, "page_size": page_size}

@app.get("/api/students", response_model=Page, tags=["Students"])
def students(db: DB, _: Annotated[User, Depends(permit(Role.SUPER_ADMIN,Role.ADMIN,Role.MANAGER,Role.TEACHER))], q: str | None=None, status_filter: StudentStatus | None=Query(None, alias="status"), page:int=Query(1,ge=1), page_size:int=Query(20,ge=1,le=100)):
    stmt=select(Student).order_by(Student.created_at.desc())
    if q: stmt=stmt.where(or_(Student.first_name.ilike(f"%{q}%"),Student.last_name.ilike(f"%{q}%"),Student.phone.ilike(f"%{q}%")))
    if status_filter: stmt=stmt.where(Student.status==status_filter)
    return paged(stmt,db,page,page_size)
@app.post("/api/students",response_model=StudentOut,status_code=201,tags=["Students"])
def create_student(data:StudentIn,db:DB,_:Annotated[User,Depends(permit(Role.SUPER_ADMIN,Role.ADMIN,Role.MANAGER))]): return save(db,Student(**data.model_dump()))
@app.get("/api/students/{id}",response_model=StudentOut,tags=["Students"])
def get_student(id:int,db:DB,_:Annotated[User,Depends(current_user)]): return entity_or_404(db,Student,id)
@app.patch("/api/students/{id}",response_model=StudentOut,tags=["Students"])
def update_student(id:int,data:StudentIn,db:DB,_:Annotated[User,Depends(permit(Role.SUPER_ADMIN,Role.ADMIN,Role.MANAGER))]):
    obj=entity_or_404(db,Student,id); [setattr(obj,k,v) for k,v in data.model_dump().items()]; return save(db,obj)
@app.delete("/api/students/{id}",status_code=204,tags=["Students"])
def archive_student(id:int,db:DB,_:Annotated[User,Depends(permit(Role.SUPER_ADMIN,Role.ADMIN))]): obj=entity_or_404(db,Student,id); obj.status=StudentStatus.ARCHIVED; save(db,obj)

def crud_routes(prefix, cls, in_model, out_model, roles, tag):
    async def list_items(db:DB, _:Annotated[User,Depends(permit(*roles))], page:int=Query(1,ge=1),page_size:int=Query(50,ge=1,le=100)): return paged(select(cls).order_by(cls.id.desc()),db,page,page_size)
    async def create_item(data:in_model,db:DB,_:Annotated[User,Depends(permit(*roles))]): return save(db,cls(**data.model_dump()))
    async def get_item(id:int,db:DB,_:Annotated[User,Depends(permit(*roles))]): return entity_or_404(db,cls,id)
    async def update_item(id:int,data:in_model,db:DB,_:Annotated[User,Depends(permit(*roles))]): obj=entity_or_404(db,cls,id); [setattr(obj,k,v) for k,v in data.model_dump().items()]; return save(db,obj)
    async def delete_item(id:int,db:DB,_:Annotated[User,Depends(permit(*roles))]): db.delete(entity_or_404(db,cls,id)); db.commit()
    app.add_api_route(prefix,list_items,methods=["GET"],response_model=Page,tags=[tag])
    app.add_api_route(prefix,create_item,methods=["POST"],response_model=out_model,status_code=201,tags=[tag])
    app.add_api_route(prefix+"/{id}",get_item,methods=["GET"],response_model=out_model,tags=[tag])
    app.add_api_route(prefix+"/{id}",update_item,methods=["PATCH"],response_model=out_model,tags=[tag])
    app.add_api_route(prefix+"/{id}",delete_item,methods=["DELETE"],status_code=204,tags=[tag])

crud_routes("/api/teachers",Teacher,TeacherIn,TeacherOut,(Role.SUPER_ADMIN,Role.ADMIN,Role.MANAGER),"Teachers")
crud_routes("/api/courses",Course,CourseIn,CourseOut,(Role.SUPER_ADMIN,Role.ADMIN,Role.MANAGER),"Courses")
crud_routes("/api/groups",Group,GroupIn,GroupOut,(Role.SUPER_ADMIN,Role.ADMIN,Role.MANAGER),"Groups")
crud_routes("/api/expenses",Expense,ExpenseIn,ExpenseOut,(Role.SUPER_ADMIN,Role.ADMIN,Role.ACCOUNTANT),"Expenses")

@app.post("/api/groups/{id}/students",status_code=201,tags=["Groups"])
def enroll(id:int,data:EnrollmentIn,db:DB,_:Annotated[User,Depends(permit(Role.SUPER_ADMIN,Role.ADMIN,Role.MANAGER))]):
    group=entity_or_404(db,Group,id); entity_or_404(db,Student,data.student_id)
    if len(group.enrollments)>=group.max_students: raise HTTPException(409,"Guruh to‘lgan")
    return save(db,GroupStudent(group_id=id,student_id=data.student_id))
@app.delete("/api/groups/{id}/students/{student_id}",status_code=204,tags=["Groups"])
def unenroll(id:int,student_id:int,db:DB,_:Annotated[User,Depends(permit(Role.SUPER_ADMIN,Role.ADMIN,Role.MANAGER))]): obj=db.get(GroupStudent,{"group_id":id,"student_id":student_id}); \
    (db.delete(obj),db.commit()) if obj else (_ for _ in ()).throw(HTTPException(404,"Biriktirish topilmadi"))

@app.get("/api/attendance",response_model=Page,tags=["Attendance"])
def attendance(db:DB,_:Annotated[User,Depends(current_user)],group_id:int|None=None,lesson_date:date|None=None,page:int=1,page_size:int=50):
    stmt=select(Attendance).order_by(Attendance.lesson_date.desc()); stmt=stmt.where(Attendance.group_id==group_id) if group_id else stmt; stmt=stmt.where(Attendance.lesson_date==lesson_date) if lesson_date else stmt; return paged(stmt,db,page,page_size)
@app.post("/api/attendance",response_model=AttendanceOut,status_code=201,tags=["Attendance"])
def mark_attendance(data:AttendanceIn,db:DB,_:Annotated[User,Depends(permit(Role.SUPER_ADMIN,Role.ADMIN,Role.MANAGER,Role.TEACHER))]):
    if not db.get(GroupStudent,{"group_id":data.group_id,"student_id":data.student_id}): raise HTTPException(422,"O‘quvchi guruhga biriktirilmagan")
    return save(db,Attendance(**data.model_dump()))
@app.get("/api/attendance/{id}",response_model=AttendanceOut,tags=["Attendance"])
def get_attendance(id:int,db:DB,_:Annotated[User,Depends(current_user)]): return entity_or_404(db,Attendance,id)
@app.patch("/api/attendance/{id}",response_model=AttendanceOut,tags=["Attendance"])
def update_attendance(id:int,data:AttendanceIn,db:DB,_:Annotated[User,Depends(permit(Role.SUPER_ADMIN,Role.ADMIN,Role.MANAGER,Role.TEACHER))]): obj=entity_or_404(db,Attendance,id); [setattr(obj,k,v) for k,v in data.model_dump().items()]; return save(db,obj)
@app.get("/api/attendance/group/{group_id}",response_model=Page,tags=["Attendance"])
def attendance_group(group_id:int,db:DB,_:Annotated[User,Depends(current_user)],page:int=1,page_size:int=100): return paged(select(Attendance).where(Attendance.group_id==group_id),db,page,page_size)

@app.get("/api/schedule",response_model=Page,tags=["Schedule"])
def schedule(db:DB,_:Annotated[User,Depends(current_user)],lesson_date:date|None=None,page:int=1,page_size:int=100): return paged(select(Schedule).where(Schedule.lesson_date==lesson_date).order_by(Schedule.start_time) if lesson_date else select(Schedule).order_by(Schedule.lesson_date,Schedule.start_time),db,page,page_size)
@app.post("/api/schedule",response_model=ScheduleOut,status_code=201,tags=["Schedule"])
def create_schedule(data:ScheduleIn,db:DB,_:Annotated[User,Depends(permit(Role.SUPER_ADMIN,Role.ADMIN,Role.MANAGER))]):
    if data.start_time>=data.end_time: raise HTTPException(422,"Boshlanish vaqti tugashdan oldin bo‘lishi kerak")
    conflict=select(Schedule).where(Schedule.lesson_date==data.lesson_date,Schedule.start_time<data.end_time,Schedule.end_time>data.start_time)
    if data.teacher_id: conflict=conflict.where(Schedule.teacher_id==data.teacher_id)
    elif data.room: conflict=conflict.where(Schedule.room==data.room)
    if db.scalar(conflict): raise HTTPException(409,"O‘qituvchi yoki xona band")
    return save(db,Schedule(**data.model_dump()))
@app.patch("/api/schedule/{id}",response_model=ScheduleOut,tags=["Schedule"])
def update_schedule(id:int,data:ScheduleIn,db:DB,_:Annotated[User,Depends(permit(Role.SUPER_ADMIN,Role.ADMIN,Role.MANAGER))]): obj=entity_or_404(db,Schedule,id); [setattr(obj,k,v) for k,v in data.model_dump().items()]; return save(db,obj)
@app.delete("/api/schedule/{id}",status_code=204,tags=["Schedule"])
def delete_schedule(id:int,db:DB,_:Annotated[User,Depends(permit(Role.SUPER_ADMIN,Role.ADMIN,Role.MANAGER))]): db.delete(entity_or_404(db,Schedule,id)); db.commit()

@app.get("/api/payments",response_model=Page,tags=["Payments"])
def payments(db:DB,_:Annotated[User,Depends(permit(Role.SUPER_ADMIN,Role.ADMIN,Role.MANAGER,Role.ACCOUNTANT))],student_id:int|None=None,page:int=1,page_size:int=50): return paged(select(Payment).where(Payment.student_id==student_id) if student_id else select(Payment).order_by(Payment.payment_date.desc()),db,page,page_size)
@app.post("/api/payments",response_model=PaymentOut,status_code=201,tags=["Payments"])
def create_payment(data:PaymentIn,db:DB,user:Annotated[User,Depends(permit(Role.SUPER_ADMIN,Role.ADMIN,Role.MANAGER,Role.ACCOUNTANT))]): entity_or_404(db,Student,data.student_id); return save(db,Payment(**data.model_dump(),received_by_id=user.id))
@app.get("/api/payments/{id}",response_model=PaymentOut,tags=["Payments"])
def get_payment(id:int,db:DB,_:Annotated[User,Depends(current_user)]): return entity_or_404(db,Payment,id)
@app.patch("/api/payments/{id}",response_model=PaymentOut,tags=["Payments"])
def update_payment(id:int,data:PaymentIn,db:DB,_:Annotated[User,Depends(permit(Role.SUPER_ADMIN,Role.ADMIN,Role.ACCOUNTANT))]): obj=entity_or_404(db,Payment,id); [setattr(obj,k,v) for k,v in data.model_dump().items()]; return save(db,obj)
@app.get("/api/payments/student/{student_id}",response_model=Page,tags=["Payments"])
def student_payments(student_id:int,db:DB,_:Annotated[User,Depends(current_user)],page:int=1,page_size:int=100): return paged(select(Payment).where(Payment.student_id==student_id),db,page,page_size)

@app.get("/api/users",response_model=Page,tags=["Users"])
def users(db:DB,_:Annotated[User,Depends(permit(Role.SUPER_ADMIN,Role.ADMIN))],page:int=1,page_size:int=50): return paged(select(User),db,page,page_size)
@app.post("/api/users",response_model=UserOut,status_code=201,tags=["Users"])
def create_user(data:UserIn,db:DB,_:Annotated[User,Depends(permit(Role.SUPER_ADMIN,Role.ADMIN))]): d=data.model_dump(); d["password_hash"]=password_hash.hash(d.pop("password")); return save(db,User(**d))
@app.get("/api/users/{id}",response_model=UserOut,tags=["Users"])
def get_user(id:int,db:DB,_:Annotated[User,Depends(permit(Role.SUPER_ADMIN,Role.ADMIN))]): return entity_or_404(db,User,id)
@app.patch("/api/users/{id}",response_model=UserOut,tags=["Users"])
def update_user(id:int,data:UserIn,db:DB,_:Annotated[User,Depends(permit(Role.SUPER_ADMIN,Role.ADMIN))]): obj=entity_or_404(db,User,id); d=data.model_dump(); d["password_hash"]=password_hash.hash(d.pop("password")); [setattr(obj,k,v) for k,v in d.items()]; return save(db,obj)
@app.delete("/api/users/{id}",status_code=204,tags=["Users"])
def deactivate_user(id:int,db:DB,_:Annotated[User,Depends(permit(Role.SUPER_ADMIN))]): obj=entity_or_404(db,User,id); obj.is_active=False; save(db,obj)

@app.get("/api/reports/dashboard",tags=["Reports"])
def dashboard(db:DB,_:Annotated[User,Depends(current_user)]):
    today=date.today(); month_start=today.replace(day=1)
    income=db.scalar(select(func.coalesce(func.sum(Payment.amount),0)).where(Payment.payment_date>=month_start)) or 0
    expenses=db.scalar(select(func.coalesce(func.sum(Expense.amount),0)).where(Expense.expense_date>=month_start)) or 0
    paid={sid:amount for sid,amount in db.execute(select(Payment.student_id,func.sum(Payment.amount)).group_by(Payment.student_id)).all()}
    debts=sum(max(Decimal(0), (e.group.monthly_fee if e.group else Decimal(0))-paid.get(e.student_id,0)) for e in db.scalars(select(GroupStudent)).all())
    return {"total_students":db.scalar(select(func.count(Student.id))) or 0,"active_students":db.scalar(select(func.count(Student.id)).where(Student.status==StudentStatus.ACTIVE)) or 0,"total_teachers":db.scalar(select(func.count(Teacher.id)).where(Teacher.is_active==True)) or 0,"active_groups":db.scalar(select(func.count(Group.id)).where(Group.status==GroupStatus.ACTIVE)) or 0,"today_lessons":db.scalar(select(func.count(Schedule.id)).where(Schedule.lesson_date==today)) or 0,"monthly_income":income,"monthly_expenses":expenses,"debt":debts,"recent_students":[StudentOut.model_validate(x).model_dump() for x in db.scalars(select(Student).order_by(Student.created_at.desc()).limit(5)).all()]}
@app.get("/api/reports/attendance",tags=["Reports"])
def attendance_report(db:DB,_:Annotated[User,Depends(current_user)],from_date:date|None=None,to_date:date|None=None):
    stmt=select(Attendance); stmt=stmt.where(Attendance.lesson_date>=from_date) if from_date else stmt; stmt=stmt.where(Attendance.lesson_date<=to_date) if to_date else stmt; rows=db.scalars(stmt).all(); total=len(rows); present=sum(x.status in (AttendanceStatus.PRESENT,AttendanceStatus.LATE) for x in rows); return {"total":total,"present":present,"rate":round(present/total*100,2) if total else 0}
@app.get("/api/reports/payments",tags=["Reports"])
def payment_report(db:DB,_:Annotated[User,Depends(permit(Role.SUPER_ADMIN,Role.ADMIN,Role.ACCOUNTANT))]): return {"total":db.scalar(select(func.coalesce(func.sum(Payment.amount),0))) or 0,"count":db.scalar(select(func.count(Payment.id))) or 0}
@app.get("/api/reports/debts",tags=["Reports"])
def debt_report(db:DB,_:Annotated[User,Depends(current_user)]): return {"message":"Qarzdorlik dashboard hisoboti tarkibida real to‘lovlar va guruh tariflari asosida hisoblanadi"}
@app.get("/api/reports/expenses",tags=["Reports"])
def expense_report(db:DB,_:Annotated[User,Depends(permit(Role.SUPER_ADMIN,Role.ADMIN,Role.ACCOUNTANT))]): return {"total":db.scalar(select(func.coalesce(func.sum(Expense.amount),0))) or 0,"count":db.scalar(select(func.count(Expense.id))) or 0}
@app.get("/api/reports/finance",tags=["Reports"])
def finance_report(db:DB,_:Annotated[User,Depends(permit(Role.SUPER_ADMIN,Role.ADMIN,Role.ACCOUNTANT))]):
    inc=db.scalar(select(func.coalesce(func.sum(Payment.amount),0))) or 0; exp=db.scalar(select(func.coalesce(func.sum(Expense.amount),0))) or 0; return {"income":inc,"expenses":exp,"net":inc-exp}
