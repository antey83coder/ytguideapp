import re
import webbrowser
import traceback

from kivy.metrics import dp
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard

from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.textfield import MDTextField
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
from kivymd.uix.label import MDLabel
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.dialog import MDDialog
from kivymd.uix.card import MDCard
from kivy.uix.image import AsyncImage
from kivy.uix.behaviors import ButtonBehavior

# =====================================================================
# КАСТОМНЕ ТЕКСТОВЕ ПОЛЕ: БУФЕР ОБМІНУ + АВТОПІДБІР БЕЗ БАГІВ
# =====================================================================
class AdvancedTextField(MDTextField):
    def __init__(self, **kwargs):
        # 1. Вмикаємо розумний автопідбір тексту Android (Т9)
        kwargs['keyboard_suggestions'] = True
        
        # 2. ТРЮК: Робимо всі поля багаторядковими, щоб Kivy не конфліктував
        # з клавіатурою Android і не дублював текст.
        if 'multiline' not in kwargs:
            kwargs['multiline'] = True
            
        if 'input_type' not in kwargs:
            kwargs['input_type'] = 'text'
            
        super().__init__(**kwargs)
        self.clipboard_menu = None

    def on_touch_down(self, touch):
        result = super().on_touch_down(touch)
        if self.collide_point(*touch.pos) and touch.is_double_tap:
            Clock.schedule_once(lambda dt: self.show_clipboard_menu(), 0.1)
        return result

    def show_clipboard_menu(self):
        menu_items = [
            {"viewclass": "OneLineListItem", "text": "✂️ Вирізати", "on_release": lambda: self.handle_action("cut")},
            {"viewclass": "OneLineListItem", "text": "📋 Копіювати", "on_release": lambda: self.handle_action("copy")},
            {"viewclass": "OneLineListItem", "text": "📥 Вставити", "on_release": lambda: self.handle_action("paste")},
        ]
        self.clipboard_menu = MDDropdownMenu(
            caller=self, 
            items=menu_items, 
            width_mult=3,
            max_height=dp(170),
            position="bottom"
        )
        self.clipboard_menu.open()

    def handle_action(self, action):
        if action == "cut":
            if self.selection_text:
                Clipboard.copy(self.selection_text)
                self.delete_selection()
            else:
                Clipboard.copy(self.text)
                self.text = ""
        elif action == "copy":
            if self.selection_text:
                Clipboard.copy(self.selection_text)
            else:
                Clipboard.copy(self.text)
        elif action == "paste":
            text_to_paste = Clipboard.paste()
            if text_to_paste:
                if self.selection_text:
                    self.delete_selection()
                self.insert_text(text_to_paste)
                
        if self.clipboard_menu:
            self.clipboard_menu.dismiss()

class ClickableThumbnail(ButtonBehavior, AsyncImage):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self.update_canvas, size=self.update_canvas)

    def update_canvas(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            from kivy.graphics import Color, RoundedRectangle
            Color(1, 1, 1, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(8), dp(8), dp(8), dp(8)])

def get_stem(word):
    word = word.lower().strip().replace('_', '')
    if len(word) <= 3:
        return word
    suffixes = (
        'ами', 'ями', 'ого', 'ому', 'ми', 'іми', 'их', 'іх', 
        'а', 'е', 'и', 'о', 'у', 'я', 'і', 'й', 'ий', 'ій', 'им', 'ім',
        'ом', 'ем', 'ею', 'ою', 'єю', 'ів', 'ем', 'ев', 'єв', 'ях', 'ах'
    )
    for suffix in suffixes:
        if word.endswith(suffix):
            stem = word[:-len(suffix)]
            if len(stem) >= 3:
                return stem
    return word

def tokenize_text(text):
    if not text:
        return []
    clean_text = text.lower().replace('_', ' ')
    return re.findall(r'\w+', clean_text)

def extract_youtube_info(url):
    try:
        import yt_dlp
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get('title', 'Без назви'), info.get('uploader', 'Невідомий канал'), info.get('thumbnail', '')
    except Exception as e:
        return "Помилка назви", "Помилка каналу", ""

class MainScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.all_records = []  
        self.themes_set = set() 
        self.dialog = None      
        self.current_edit_id = None 
        self.menu = None
        
        self.table = None
        
        main_layout = MDBoxLayout(orientation='vertical')
        
        header = MDBoxLayout(size_hint_y=None, height=dp(56), md_bg_color=[0.12, 0.58, 0.95, 1], padding=[dp(16), 0, dp(16), 0])
        header.add_widget(MDLabel(
            text="YT Personal Guide", font_style="H6", halign="center", 
            theme_text_color="Custom", text_color=[1, 1, 1, 1], bold=True
        ))
        main_layout.add_widget(header)
        
        scroll = MDScrollView(do_scroll_x=False)
        content_layout = MDBoxLayout(orientation='vertical', padding=dp(16), spacing=dp(16), adaptive_height=True)
        
        url_layout = MDBoxLayout(orientation='horizontal', spacing=dp(10), size_hint_y=None, height=dp(68))
        self.input_url = AdvancedTextField(hint_text="Посилання на YouTube", mode="rectangle", size_hint_x=1, input_type='url')
        
        btn_paste = MDIconButton(
            icon="content-paste",
            pos_hint={"center_y": .5},
            on_release=self.paste_from_clipboard
        )
        
        url_layout.add_widget(self.input_url)
        url_layout.add_widget(btn_paste)
        content_layout.add_widget(url_layout)
        
        self.input_theme = AdvancedTextField(hint_text="Тема (клікніть для списку)", mode="rectangle", size_hint_y=None, height=dp(68))
        self.input_theme.bind(on_touch_down=self.on_theme_field_click)
        content_layout.add_widget(self.input_theme)
        
        self.input_subtheme = AdvancedTextField(hint_text="Підтема", mode="rectangle", size_hint_y=None, height=dp(68))
        content_layout.add_widget(self.input_subtheme)
        
        self.input_keywords = AdvancedTextField(hint_text="Ключові слова", mode="rectangle", size_hint_y=None, height=dp(68))
        content_layout.add_widget(self.input_keywords)
        
        self.input_notes = AdvancedTextField(hint_text="Нотатки / Короткий зміст", mode="rectangle", size_hint_y=None, height=dp(100))
        content_layout.add_widget(self.input_notes)
        
        self.btn_add = MDRaisedButton(text="ЗБЕРЕГТИ В КАТАЛОГ", size_hint_x=1, size_hint_y=None, height=dp(50))
        self.btn_add.bind(on_release=self.process_add_video)
        content_layout.add_widget(self.btn_add)
        
        self.status_label = MDLabel(text="Запуск інтерфейсу...", halign="center", theme_text_color="Secondary", size_hint_y=None, height=dp(40))
        self.status_label.bind(width=lambda *x: self.status_label.setter('text_size')(self.status_label, (self.status_label.width, None)))
        self.status_label.bind(texture_size=lambda *x: self.status_label.setter('height')(self.status_label, max(self.status_label.texture_size[1], dp(40))))
        content_layout.add_widget(self.status_label)
        
        self.search_field = AdvancedTextField(hint_text="🔍 Пошук по базі...", mode="fill", size_hint_y=None, height=dp(60))
        self.search_field.bind(text=self.on_search_text_change)
        content_layout.add_widget(self.search_field)
        
        self.video_list = MDBoxLayout(orientation='vertical', adaptive_height=True, spacing=dp(10))
        content_layout.add_widget(self.video_list)
        
        scroll.add_widget(content_layout)
        main_layout.add_widget(scroll)
        self.add_widget(main_layout)
        
        Clock.schedule_once(self.delayed_init, 1.0)

    def paste_from_clipboard(self, instance):
        pasted_text = Clipboard.paste()
        if pasted_text:
            self.input_url.text = pasted_text

    def delayed_init(self, dt):
        try:
            self.status_label.text = "Підключення до Airtable..."
            self.status_label.theme_text_color = "Secondary"
            from pyairtable import Table
            
            TOKEN = "patRPP4JMXbbOfL0f.b89351374308e546fb099221ed2aa459907c98740b56ac7843990c376cbc911b"
            BASE_ID = "appH9W7WJOHDC1wdH"
            TABLE_NAME = "Відео"
            
            self.table = Table(TOKEN, BASE_ID, TABLE_NAME)
            self.load_data_from_base()
        except Exception as e:
            self.status_label.theme_text_color = "Error"
            self.status_label.text = f"Помилка інтернету або бази:\n{e}"

    def load_data_from_base(self):
        if not self.table: return
        try:
            self.status_label.text = "Синхронізація..."
            self.all_records = self.table.all()
            self.themes_set.clear()
            self.display_records(self.all_records)
            
            for record in self.all_records:
                theme = record.get('fields', {}).get("Тема")
                if theme: self.themes_set.add(theme)
                    
            self.update_theme_menu()
            self.status_label.theme_text_color = "Primary"
            self.status_label.text = "Каталог успішно синхронізовано."
        except Exception as e:
            self.status_label.theme_text_color = "Error"
            self.status_label.text = f"Помилка зв'язку: {e}"

    def display_records(self, records_list):
        self.video_list.clear_widgets()
        for record in records_list:
            fields = record.get('fields', {})
            title = fields.get("Назва відео", "Без назви")
            video_url = fields.get("Посилання", "")
            img_url = fields.get("Опис", "") 
            rec_id = record.get('id')
            
            if not img_url or not img_url.startswith("http"):
                img_url = "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=200"

            card = MDCard(
                orientation='horizontal', padding=dp(8), spacing=dp(12), size_hint_y=None, height=dp(90), 
                elevation=2, radius=[dp(8)], md_bg_color=[0.15, 0.15, 0.15, 1]
            )
            
            thumb = ClickableThumbnail(source=img_url, size_hint_x=None, width=dp(110), allow_stretch=True, keep_ratio=False)
            thumb.bind(on_release=lambda x, url=video_url: webbrowser.open(url))
            
            text_layout = MDBoxLayout(orientation='vertical', pos_hint={"center_y": .5})
            title_btn = MDFlatButton(
                text=title if len(title) < 50 else f"{title[:47]}...",
                theme_text_color="Custom", text_color=[0.9, 0.9, 0.9, 1], halign="left", pos_hint={"x": 0}
            )
            title_btn.bind(on_release=lambda x, r_id=rec_id: self.open_edit_dialog(r_id))
            
            text_layout.add_widget(title_btn)
            card.add_widget(thumb)
            card.add_widget(text_layout)
            self.video_list.add_widget(card)

    def on_search_text_change(self, instance, text):
        query_text = text.strip()
        if not query_text:
            self.display_records(self.all_records)
            return
            
        query_stems = [get_stem(w) for w in tokenize_text(query_text)]
        filtered_records = []
        
        for record in self.all_records:
            fields = record.get('fields', {})
            search_zone_text = " ".join([
                fields.get('Назва відео', ''), fields.get('Опис', ''),
                fields.get('Ключові слова', ''), fields.get('Нотатки', ''),
                fields.get('Тема', ''), fields.get('Підтема', '')
            ])
            base_stems = [get_stem(w) for w in tokenize_text(search_zone_text)]
            
            match = True
            for q_stem in query_stems:
                if not any(q_stem in b_stem or b_stem in q_stem for b_stem in base_stems):
                    match = False
                    break
            if match: filtered_records.append(record)
                
        self.display_records(filtered_records)

    def update_theme_menu(self):
        if not self.themes_set: return
        menu_items = [
            {"viewclass": "OneLineListItem", "text": theme, "on_release": lambda x=theme: self.set_theme(x)}
            for theme in sorted(list(self.themes_set))
        ]
        self.menu = MDDropdownMenu(caller=self.input_theme, items=menu_items, width_mult=4, max_height=dp(250))

    def on_theme_field_click(self, instance, touch):
        if instance.collide_point(*touch.pos):
            if self.menu and not touch.is_double_tap:
                self.menu.open()

    def set_theme(self, theme_text):
        self.input_theme.text = theme_text
        if self.menu: self.menu.dismiss()

    def process_add_video(self, instance):
        url = self.input_url.text.strip()
        theme = self.input_theme.text.strip()
        subtheme = self.input_subtheme.text.strip()
        keywords = self.input_keywords.text.strip()
        notes = self.input_notes.text.strip()
        
        if not url or not theme or not self.table:
            return

        self.status_label.theme_text_color = "Primary"
        self.status_label.text = "Обробка відео..."
        title, channel, thumbnail = extract_youtube_info(url)
        
        try:
            self.table.create({
                "Посилання": url, "Назва відео": title, "Канал": channel,
                "Тема": theme, "Підтема": subtheme, "Опис": thumbnail,
                "Ключові слова": keywords, "Нотатки": notes
            })
            self.input_url.text = ""
            self.input_notes.text = ""
            self.load_data_from_base()
        except Exception as e:
            self.status_label.theme_text_color = "Error"
            self.status_label.text = f"Помилка збереження: {e}"

    def open_edit_dialog(self, record_id):
        self.current_edit_id = record_id
        target_fields = None
        for r in self.all_records:
            if r.get('id') == record_id:
                target_fields = r.get('fields', {})
                break
        if not target_fields: return
            
        self.edit_subtheme = AdvancedTextField(text=target_fields.get('Підтема', ''), hint_text="Редагувати підтему", mode="rectangle", size_hint_y=None, height=dp(68))
        self.edit_keywords = AdvancedTextField(text=target_fields.get('Ключові слова', ''), hint_text="Редагувати ключові слова", mode="rectangle", size_hint_y=None, height=dp(68))
        self.edit_notes = AdvancedTextField(text=target_fields.get('Нотатки', ''), hint_text="Редагувати нотатки", mode="rectangle", size_hint_y=None, height=dp(100))
        
        dialog_layout = MDBoxLayout(orientation="vertical", spacing=dp(12), size_hint_y=None, height=dp(260))
        dialog_layout.add_widget(self.edit_subtheme)
        dialog_layout.add_widget(self.edit_keywords)
        dialog_layout.add_widget(self.edit_notes)
        
        self.dialog = MDDialog(
            title="Редагування", type="custom", content_cls=dialog_layout,
            buttons=[
                MDFlatButton(text="ВИДАЛИТИ", theme_text_color="Error", on_release=self.delete_record),
                MDFlatButton(text="СКАСУВАТИ", on_release=lambda x: self.dialog.dismiss()),
                MDRaisedButton(text="ЗБЕРЕГТИ", on_release=self.save_edited_data),
            ],
        )
        self.dialog.open()

    def save_edited_data(self, instance):
        new_subtheme = self.edit_subtheme.text.strip()
        new_keywords = self.edit_keywords.text.strip()
        new_notes = self.edit_notes.text.strip()
        self.dialog.dismiss()
        
        if not self.table: return
        
        try:
            self.table.update(self.current_edit_id, {
                "Підтема": new_subtheme, "Ключові слова": new_keywords, "Нотатки": new_notes
            })
            self.load_data_from_base()
        except Exception as e:
            self.status_label.theme_text_color = "Error"
            self.status_label.text = f"Помилка: {e}"

    def delete_record(self, instance):
        self.dialog.dismiss()
        if not self.current_edit_id or not self.table:
            return
            
        try:
            self.table.delete(self.current_edit_id)
            self.status_label.theme_text_color = "Primary"
            self.status_label.text = "Відео успішно видалено."
            self.load_data_from_base()
        except Exception as e:
            self.status_label.theme_text_color = "Error"
            self.status_label.text = f"Помилка видалення: {e}"

class YouTubeCatalogApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.theme_style = "Dark"
        return MainScreen()

if __name__ == '__main__':
    YouTubeCatalogApp().run()
