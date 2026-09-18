"""Тесты данных и веб-интерфейса CRM."""

import threading
import unittest
import urllib.request

from app import (
    APP_ICON_PATH,
    APP_TITLE,
    COMPANY_LOGO_PATH,
    create_server,
    load_partner_cards,
    render_page,
    split_partner_name,
)


class PartnerUITests(unittest.TestCase):
    def test_window_title_matches_purpose(self) -> None:
        self.assertEqual(APP_TITLE, "CRM: Список партнёров и скидок")

    def test_partner_name_is_split_into_type_and_name(self) -> None:
        self.assertEqual(split_partner_name("ООО Альфа"), ("ООО", "Альфа"))
        self.assertEqual(split_partner_name("Партнёр"), ("Партнёр", "Партнёр"))

    def test_cards_are_loaded_from_database_with_discounts(self) -> None:
        cards = load_partner_cards()
        self.assertEqual(len(cards), 5)
        self.assertEqual(
            [card.discount_percent for card in cards],
            [0, 5, 10, 15, 0],
        )
        self.assertEqual(
            [card.total_quantity for card in cards],
            [9_999, 49_999, 299_999, 300_000, 0],
        )

    def test_page_contains_title_logo_icon_and_all_cards(self) -> None:
        page = render_page(load_partner_cards())
        self.assertIn(f"<title>{APP_TITLE}</title>", page)
        self.assertIn("resources/app_icon.svg", page)
        self.assertIn("resources/company_logo.svg", page)
        self.assertEqual(page.count('class="partner-card"'), 5)
        self.assertIn("300 000 ед.", page)
        self.assertIn("15%", page)

    def test_logo_and_icon_are_valid_svg_resources(self) -> None:
        for image_path in (APP_ICON_PATH, COMPANY_LOGO_PATH):
            with self.subTest(image=image_path.name):
                self.assertTrue(image_path.is_file())
                self.assertIn("<svg", image_path.read_text(encoding="utf-8"))

    def test_http_server_returns_rendered_page_and_styles(self) -> None:
        server = create_server(port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            with urllib.request.urlopen(f"http://{host}:{port}/") as response:
                page = response.read().decode("utf-8")
            with urllib.request.urlopen(f"http://{host}:{port}/styles.css") as response:
                styles = response.read().decode("utf-8")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertIn(APP_TITLE, page)
        self.assertIn(".partner-card", styles)
        self.assertIn("#ec007a", styles.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
