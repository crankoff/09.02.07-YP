from pathlib import Path
import sqlite3
import tempfile
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app import create_server
from create_database import create_demo_database
from database import (
    PartnerRepository,
    ReferentialIntegrityError,
    connect_database,
)
from windows import MainWindow, PartnerEditWindow


class CrudApplicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "test.db"
        create_demo_database(self.database_path)
        self.server = create_server(port=0, database_path=self.database_path)
        self.server_thread = Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=5)
        self.temporary_directory.cleanup()

    def get_page(self, path: str) -> str:
        with urlopen(f"{self.base_url}{path}", timeout=5) as response:
            return response.read().decode("utf-8")

    def test_windows_have_unique_titles(self) -> None:
        self.assertNotEqual(
            MainWindow.window_title,
            PartnerEditWindow.add_window_title,
        )
        self.assertNotEqual(
            PartnerEditWindow.add_window_title,
            PartnerEditWindow.edit_window_title,
        )

    def test_main_window_opens_add_window(self) -> None:
        page = self.get_page("/")
        self.assertIn("<title>CRM: Реестр партнёров</title>", page)
        self.assertIn('href="/partner/new"', page)
        self.assertEqual(page.count('class="partner-card"'), 3)
        self.assertIn('href="/partner/1/edit"', page)

    def test_add_window_has_back_navigation(self) -> None:
        page = self.get_page("/partner/new")
        self.assertIn("CRM: Карточка партнёра [Добавление]", page)
        self.assertIn('formaction="/partner/cancel"', page)
        self.assertIn(">Назад</button>", page)

    def test_form_contains_all_required_fields_and_hints(self) -> None:
        page = self.get_page("/partner/new")
        for field_name in (
            "name",
            "partner_type",
            "rating",
            "address",
            "director",
            "phone",
            "email",
        ):
            self.assertIn(f'name="{field_name}"', page)
        for partner_type in ("ЗАО", "ООО", "ИП", "АО", "ПАО"):
            self.assertIn(f'value="{partner_type}"', page)
        self.assertIn("+7 900 000-00-00", page)
        self.assertIn("name@company.ru", page)

    def test_edit_window_has_editing_title(self) -> None:
        page = self.get_page("/partner/1/edit")
        self.assertIn("CRM: Карточка партнёра [Редактирование]", page)
        self.assertIn("Альфа Снаб", page)
        self.assertIn("г. Москва, ул. Деловая, д. 12", page)
        self.assertIn('action="/partner/delete"', page)

    def test_new_partner_is_saved_and_state_is_preserved(self) -> None:
        form = urlencode(
            {
                "partner_id": "",
                "partner_type": "ООО",
                "name": "Навигация Тест",
                "address": "г. Москва, ул. Тестовая, д. 1",
                "director": "Тестов Тест Тестович",
                "phone": "+7 900 000-00-00",
                "email": "navigation@test.example",
                "rating": "9",
            }
        ).encode("utf-8")
        request = Request(
            f"{self.base_url}/partner/save",
            data=form,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urlopen(request, timeout=5) as response:
            page = response.read().decode("utf-8")
        self.assertIn("Навигация Тест", page)
        self.assertIn("Партнёр добавлен", page)
        self.assertIn('system-dialog--information', page)
        self.assertIn(">Информация<", page)
        self.assertEqual(page.count('class="partner-card"'), 4)
        self.assertEqual(len(PartnerRepository(self.database_path).list_all()), 4)
        self.assertIn("Навигация Тест", self.get_page("/"))

    def test_existing_partner_can_be_edited(self) -> None:
        form = urlencode(
            {
                "partner_id": "1",
                "partner_type": "ЗАО",
                "name": "Альфа Снаб Обновлённая",
                "address": "г. Москва, ул. Новая, д. 5",
                "director": "Соколов Артём Ильич",
                "phone": "+7 900 111-22-33",
                "email": "updated@alpha-snab.example",
                "rating": "12",
            }
        ).encode("utf-8")
        request = Request(f"{self.base_url}/partner/save", data=form, method="POST")
        with urlopen(request, timeout=5) as response:
            page = response.read().decode("utf-8")
        updated_partner = PartnerRepository(self.database_path).get(1)
        self.assertIn("Альфа Снаб Обновлённая", page)
        self.assertIn("Данные партнёра обновлены", page)
        self.assertEqual(updated_partner.address, "г. Москва, ул. Новая, д. 5")
        self.assertEqual(updated_partner.rating, 12)
        self.assertEqual(updated_partner.sales_count, 2)

    def test_partner_without_sales_can_be_deleted(self) -> None:
        request = Request(
            f"{self.base_url}/partner/delete",
            data=urlencode({"partner_id": "3"}).encode("utf-8"),
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            page = response.read().decode("utf-8")
        self.assertIn("Партнёр удалён", page)
        self.assertNotIn("Городские решения", page)
        self.assertIsNone(PartnerRepository(self.database_path).get(3))

    def test_partner_with_sales_cannot_be_deleted(self) -> None:
        request = Request(
            f"{self.base_url}/partner/delete",
            data=urlencode({"partner_id": "1"}).encode("utf-8"),
            method="POST",
        )
        with self.assertRaises(HTTPError) as context:
            urlopen(request, timeout=5)
        page = context.exception.read().decode("utf-8")
        self.assertEqual(context.exception.code, 409)
        self.assertIn("есть история продаж", page)
        self.assertIsNotNone(PartnerRepository(self.database_path).get(1))

    def test_repository_checks_referential_integrity_before_delete(self) -> None:
        repository = PartnerRepository(self.database_path)
        with self.assertRaises(ReferentialIntegrityError):
            repository.delete(2)
        self.assertIsNotNone(repository.get(2))

    def test_database_foreign_key_is_active(self) -> None:
        with connect_database(self.database_path) as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO sales_history (partner_id, sale_date, quantity)
                    VALUES (9999, '2026-09-25', 1)
                    """
                )

    def test_phone_format_is_validated(self) -> None:
        form = urlencode(
            {
                "partner_id": "",
                "partner_type": "ООО",
                "name": "Тест",
                "address": "г. Москва",
                "director": "Тестов Тест",
                "phone": "9000000000",
                "email": "test@example.com",
                "rating": "1",
            }
        ).encode("utf-8")
        request = Request(f"{self.base_url}/partner/save", data=form, method="POST")
        with self.assertRaises(HTTPError) as context:
            urlopen(request, timeout=5)
        self.assertIn(
            "+7 900 000-00-00",
            context.exception.read().decode("utf-8"),
        )

    def test_noninteger_rating_shows_error_dialog(self) -> None:
        form = urlencode(
            {
                "partner_id": "",
                "partner_type": "ООО",
                "name": "Тест",
                "address": "г. Москва",
                "director": "Тестов Тест",
                "phone": "+7 900 000-00-00",
                "email": "test@example.com",
                "rating": "пять!",
            }
        ).encode("utf-8")
        request = Request(f"{self.base_url}/partner/save", data=form, method="POST")
        with self.assertRaises(HTTPError) as context:
            urlopen(request, timeout=5)
        page = context.exception.read().decode("utf-8")
        self.assertEqual(context.exception.code, 422)
        self.assertIn('system-dialog--error', page)
        self.assertIn(">Ошибка<", page)
        self.assertIn("Удалите буквы и знаки препинания", page)

    def test_changed_form_shows_warning_before_exit(self) -> None:
        form = urlencode(
            {
                "partner_id": "1",
                "partner_type": "ООО",
                "name": "Изменённое название",
                "address": "г. Москва, ул. Деловая, д. 12",
                "director": "Соколов Артём Ильич",
                "phone": "+7 900 111-22-33",
                "email": "info@alpha-snab.example",
                "rating": "8",
            }
        ).encode("utf-8")
        request = Request(f"{self.base_url}/partner/cancel", data=form, method="POST")
        with urlopen(request, timeout=5) as response:
            page = response.read().decode("utf-8")
        self.assertIn('system-dialog--warning', page)
        self.assertIn(">Предупреждение<", page)
        self.assertIn("Выйти без сохранения", page)
        self.assertIn("Продолжить редактирование", page)
        self.assertEqual(PartnerRepository(self.database_path).get(1).name, "Альфа Снаб")

    def test_unchanged_form_returns_without_warning(self) -> None:
        form = urlencode(
            {
                "partner_id": "1",
                "partner_type": "ООО",
                "name": "Альфа Снаб",
                "address": "г. Москва, ул. Деловая, д. 12",
                "director": "Соколов Артём Ильич",
                "phone": "+7 900 111-22-33",
                "email": "info@alpha-snab.example",
                "rating": "8",
            }
        ).encode("utf-8")
        request = Request(f"{self.base_url}/partner/cancel", data=form, method="POST")
        with urlopen(request, timeout=5) as response:
            page = response.read().decode("utf-8")
        self.assertIn("Реестр партнёров", page)
        self.assertNotIn('system-dialog--warning', page)

    def test_database_failure_shows_error_dialog(self) -> None:
        missing_database = Path(self.temporary_directory.name) / "missing.db"
        server = create_server(port=0, database_path=missing_database)
        server_thread = Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        try:
            with self.assertRaises(HTTPError) as context:
                urlopen(f"http://127.0.0.1:{server.server_port}/", timeout=5)
            page = context.exception.read().decode("utf-8")
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=5)
        self.assertEqual(context.exception.code, 503)
        self.assertIn('system-dialog--error', page)
        self.assertIn("База данных недоступна", page)

    def test_invalid_form_stays_on_edit_window_with_error(self) -> None:
        request = Request(
            f"{self.base_url}/partner/save",
            data=urlencode({"name": "Черновик", "rating": "15"}).encode("utf-8"),
            method="POST",
        )
        with self.assertRaises(HTTPError) as context:
            urlopen(request, timeout=5)
        page = context.exception.read().decode("utf-8")
        self.assertEqual(context.exception.code, 422)
        self.assertIn("обязательные поля не должны быть пустыми", page)
        self.assertIn('system-dialog--error', page)
        self.assertIn("Черновик", page)


if __name__ == "__main__":
    unittest.main(verbosity=2)
