"""简易图书管理系统，全部在这一个文件里。

先注册，再登录。登录后可以查看图书、借书、还书。
用户、图书、借阅都写在本文件底部的数据区，关掉再开还在。

运行：python library.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from getpass import getpass
from pathlib import Path

BEGIN = "@" + "@BEGIN@@\n"
END = "\n@" + "@END@@"


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def pad(text: str, width: int) -> str:
    size = sum(2 if ord(ch) > 127 else 1 for ch in text)
    return text + " " * max(0, width - size)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


@dataclass
class User:
    id: int
    name: str
    password: str


@dataclass
class Book:
    id: int
    title: str
    author: str
    total: int
    available: int


@dataclass
class Loan:
    id: int
    user_id: int
    book_id: int
    borrowed_at: str
    returned_at: str | None = None


class Library:
    def __init__(self) -> None:
        self.users: list[User] = []
        self.books: list[Book] = []
        self.loans: list[Loan] = []
        self._next_user_id = 1
        self._next_book_id = 1
        self._next_loan_id = 1

    def register(self, name: str, password: str) -> User:
        name = name.strip()
        if not name:
            raise ValueError("用户名不能为空")
        if not password:
            raise ValueError("密码不能为空")
        if any(user.name == name for user in self.users):
            raise ValueError("这个用户名已经注册过了")
        user = User(self._next_user_id, name, hash_password(password))
        self._next_user_id += 1
        self.users.append(user)
        return user

    def login(self, name: str, password: str) -> User:
        name = name.strip()
        digest = hash_password(password)
        for user in self.users:
            if user.name == name and user.password == digest:
                return user
        raise ValueError("用户名或密码不正确")

    def add_book(self, title: str, author: str, total: int) -> Book:
        title = title.strip()
        author = author.strip()
        if not title or not author:
            raise ValueError("书名和作者不能为空")
        if total < 1:
            raise ValueError("册数至少为 1")
        book = Book(self._next_book_id, title, author, total, total)
        self._next_book_id += 1
        self.books.append(book)
        return book

    def find_user(self, user_id: int) -> User | None:
        return next((user for user in self.users if user.id == user_id), None)

    def find_book(self, book_id: int) -> Book | None:
        return next((book for book in self.books if book.id == book_id), None)

    def active_loans(self, user_id: int | None = None) -> list[Loan]:
        loans = [loan for loan in self.loans if loan.returned_at is None]
        if user_id is not None:
            loans = [loan for loan in loans if loan.user_id == user_id]
        return loans

    def borrow(self, user_id: int, book_id: int) -> Loan:
        user = self.find_user(user_id)
        if user is None:
            raise ValueError("请先注册并登录")
        book = self.find_book(book_id)
        if book is None:
            raise ValueError(f"找不到图书 {book_id}")
        if book.available < 1:
            raise ValueError(f"《{book.title}》已全部借出")
        if any(loan.book_id == book_id for loan in self.active_loans(user_id)):
            raise ValueError(f"你已经借了《{book.title}》，请先归还")
        book.available -= 1
        loan = Loan(self._next_loan_id, user_id, book_id, now_text())
        self._next_loan_id += 1
        self.loans.append(loan)
        return loan

    def give_back(self, loan_id: int, user_id: int) -> Loan:
        loan = next((item for item in self.loans if item.id == loan_id), None)
        if loan is None or loan.user_id != user_id:
            raise ValueError("找不到这条借阅，或不是你借的")
        if loan.returned_at is not None:
            raise ValueError("这本书已经还过了")
        book = self.find_book(loan.book_id)
        if book is None:
            raise ValueError("对应图书不存在")
        book.available += 1
        loan.returned_at = now_text()
        return loan

    def to_dict(self) -> dict:
        return {
            "next_user_id": self._next_user_id,
            "next_book_id": self._next_book_id,
            "next_loan_id": self._next_loan_id,
            "users": [asdict(user) for user in self.users],
            "books": [asdict(book) for book in self.books],
            "loans": [asdict(loan) for loan in self.loans],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Library:
        library = cls()
        library._next_user_id = data["next_user_id"]
        library._next_book_id = data["next_book_id"]
        library._next_loan_id = data["next_loan_id"]
        library.users = [User(**item) for item in data["users"]]
        library.books = [Book(**item) for item in data["books"]]
        library.loans = [Loan(**item) for item in data["loans"]]
        return library

    def save(self) -> None:
        path = Path(__file__).resolve()
        text = path.read_text(encoding="utf-8")
        start = text.index(BEGIN) + len(BEGIN)
        stop = text.index(END, start)
        payload = json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
        updated = text[:start] + payload + text[stop:]
        temporary = path.with_suffix(".py.tmp")
        temporary.write_text(updated, encoding="utf-8")
        temporary.replace(path)

    @classmethod
    def load(cls) -> Library:
        text = Path(__file__).read_text(encoding="utf-8")
        start = text.index(BEGIN) + len(BEGIN)
        stop = text.index(END, start)
        return cls.from_dict(json.loads(text[start:stop]))


def ask(prompt: str) -> str:
    return input(prompt).strip()


def ask_secret(prompt: str) -> str:
    try:
        return getpass(prompt).strip()
    except Exception:
        return ask(prompt)


def ask_int(prompt: str) -> int:
    text = ask(prompt)
    if not text.isdigit():
        raise ValueError("请输入正整数编号")
    return int(text)


def print_books(library: Library) -> None:
    if not library.books:
        print("还没有图书。")
        return
    print(f"{pad('编号', 8)}{pad('书名', 16)}{pad('作者', 14)}在馆/总数")
    print("-" * 46)
    for book in library.books:
        print(
            f"{pad(str(book.id), 8)}{pad(book.title, 16)}{pad(book.author, 14)}"
            f"{book.available}/{book.total}"
        )


def print_loans(library: Library, loans: list[Loan]) -> None:
    if not loans:
        print("没有借阅记录。")
        return
    print(f"{pad('记录', 8)}{pad('书名', 16)}{pad('借出', 18)}归还")
    print("-" * 52)
    for loan in loans:
        book = library.find_book(loan.book_id)
        title = book.title if book else "?"
        returned = loan.returned_at or "未还"
        print(
            f"{pad(str(loan.id), 8)}{pad(title, 16)}"
            f"{pad(loan.borrowed_at, 18)}{returned}"
        )


def register_user(library: Library) -> None:
    name = ask("用户名: ")
    password = ask_secret("密码: ")
    again = ask_secret("再输入一次密码: ")
    if password != again:
        raise ValueError("两次密码不一致")
    user = library.register(name, password)
    library.save()
    print(f"注册成功，欢迎 {user.name}。请登录后再借书。")


def add_book(library: Library) -> None:
    title = ask("书名: ")
    author = ask("作者: ")
    total = ask_int("册数: ")
    book = library.add_book(title, author, total)
    library.save()
    print(f"已添加《{book.title}》，编号 {book.id}")


def borrow_book(library: Library, user: User) -> None:
    print_books(library)
    book_id = ask_int("图书编号: ")
    loan = library.borrow(user.id, book_id)
    library.save()
    book = library.find_book(loan.book_id)
    print(f"借出《{book.title}》，记录编号 {loan.id}")


def return_book(library: Library, user: User) -> None:
    loans = library.active_loans(user.id)
    print_loans(library, loans)
    if not loans:
        return
    loan_id = ask_int("要归还的记录编号: ")
    loan = library.give_back(loan_id, user.id)
    library.save()
    book = library.find_book(loan.book_id)
    print(f"已归还《{book.title}》")


def user_menu(library: Library, user: User) -> None:
    actions = {
        "1": ("查看图书", lambda: print_books(library)),
        "2": ("借书", lambda: borrow_book(library, user)),
        "3": ("还书", lambda: return_book(library, user)),
        "4": ("我的借阅", lambda: print_loans(library, [loan for loan in library.loans if loan.user_id == user.id])),
        "5": ("添加图书", lambda: add_book(library)),
    }
    while True:
        print()
        print(f"当前用户：{user.name}")
        for key, (label, _) in actions.items():
            print(f"  {key}. {label}")
        print("  0. 退出登录")
        choice = ask("请选择: ")
        if choice == "0":
            print("已退出登录。")
            return
        action = actions.get(choice)
        if action is None:
            print("没有这个选项。")
            continue
        try:
            action[1]()
        except ValueError as exc:
            print(f"操作失败：{exc}")


def login_user(library: Library) -> None:
    if not library.users:
        print("还没有用户，请先注册。")
        return
    name = ask("用户名: ")
    password = ask_secret("密码: ")
    user = library.login(name, password)
    print(f"登录成功，{user.name}")
    user_menu(library, user)


def menu() -> None:
    library = Library.load()
    print("简易图书管理系统")
    print("请先注册，再登录。")
    while True:
        print()
        print("  1. 注册")
        print("  2. 登录")
        print("  0. 退出")
        choice = ask("请选择: ")
        if choice == "0":
            print("已退出。")
            return
        try:
            if choice == "1":
                register_user(library)
            elif choice == "2":
                login_user(library)
            else:
                print("没有这个选项。")
        except ValueError as exc:
            print(f"操作失败：{exc}")


def setup_console() -> None:
    for stream in (sys.stdout, sys.stderr, sys.stdin):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except Exception:
            pass


if __name__ == "__main__":
    setup_console()
    menu()


_DATA = r"""
@@BEGIN@@
{
  "next_user_id": 1,
  "next_book_id": 7,
  "next_loan_id": 1,
  "users": [],
  "books": [
    {
      "id": 1,
      "title": "星港夜航",
      "author": "林晚舟",
      "total": 2,
      "available": 2
    },
    {
      "id": 2,
      "title": "雨巷茶馆",
      "author": "陈小满",
      "total": 1,
      "available": 1
    },
    {
      "id": 3,
      "title": "北窗手记",
      "author": "周衡",
      "total": 3,
      "available": 3
    },
    {
      "id": 4,
      "title": "雾中车站",
      "author": "苏青禾",
      "total": 2,
      "available": 2
    },
    {
      "id": 5,
      "title": "山河小厨",
      "author": "赵南山",
      "total": 1,
      "available": 1
    },
    {
      "id": 6,
      "title": "灯塔来信",
      "author": "顾清",
      "total": 2,
      "available": 2
    }
  ],
  "loans": []
}
@@END@@
"""
