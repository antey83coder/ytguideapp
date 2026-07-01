import traceback

try:
    import re
    import webbrowser
    from pyairtable import Api
    import yt_dlp

    from kivymd.app import MDApp
    from kivymd.uix.screen import MDScreen
    from kivymd.uix.boxlayout import MDBoxLayout
    from kivymd.uix.scrollview import MDScrollView
    from kivymd.uix.textfield import MDTextField
    from kivymd.uix.button import MDRaisedButton, MDFlatButton
    from kivymd.uix.label import MDLabel
    from kivymd.uix.list import MDList
    from kivymd.uix.menu import MDDropdownMenu
    from kivymd.uix.dialog import MDDialog
    from kivymd.uix.card import MDCard
    from kivy.uix.image import AsyncImage
    from kivy.uix.behaviors import ButtonBehavior
    from kivy.uix.widget import Widget

    class ClickableThumbnail(ButtonBehavior, AsyncImage):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.bind(pos=self.update_canvas, size=self.update_canvas)

        def update_canvas(self, *args):
            self.canvas.before.clear()
            with self.canvas.before:
                from kivy.graphics import Color, RoundedRectangle
                Color(1, 1, 1, 1)
                RoundedRectangle(pos=self.pos, size=self.size, radius=[8, 8, 8, 8])

    # =====================================================================
    # АЛГОРИТМ РОЗУМНОГО ПОШУКУ
    # =====================================================================
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

    # =====================================================================
    # НАЛАШТУВАННЯ БАЗИ ДАНИХ
    # =====================================================================
    TOKEN = "patRPP4JMXbbOfL0f.b89351374308e546fb099221ed2aa459907c98740b56ac7843990c376cbc911b"
    BASE_ID = "appH9W7WJOHDC1wdH"
    TABLE_NAME = "Відео"

    api = Api(TOKEN)
    table = api.table(BASE_ID, TABLE_NAME)

    def extract_youtube_info(url):
        ydl_opts = {'quiet': True, 'no_warnings': True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info.get('title', 'Без назви'), info.get('uploader', 'Невідомий канал'), info.get('thumbnail', '')
        except Exception as e:
            return "Помилка назви", "Помилка каналу", ""

    # =====================================================================
    # ГОЛОВНИЙ ЕКРАН ДОДАТКА
    # =====================================================================
    class MainScreen(MDScreen):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.all_records = []  
            self.themes_set = set() 
            self.dialog = None      
            self.current_edit_id = None 
            self.menu = None
            
            main_layout = MDBoxLayout(orientation='vertical', padding=[16, 8, 16, 8], spacing=0)
            
            main_layout.add_widget(MDLabel(
                text="🎬 YT Personal Guide", font_style="Subtitle2", halign="center", size_hint_y=None, height=24
            ))
            main_layout.add_widget(Widget(size_hint_y=None, height=10))
            
            self.input_url = MDTextField(hint_text="Посилання на YouTube", mode="rectangle", size_hint_y=None, height=30)
            main_layout.add_widget(self.input_url)
            main_layout.add_widget(Widget(size_hint_y=None, height=10)) 
            
            self.input_theme = MDTextField(hint_text="Тема (клікніть для списку або впишіть нову)", mode="rectangle", size_hint_y=None, height=30)
            self.input_theme.bind(on_touch_down=self.on_theme_field_click)
            main_layout.add_widget(self.input_theme)
            main_layout.add_widget(Widget(size_hint_y=None, height=10)) 
            
            self.input_subtheme = MDTextField(hint_text="Підтема", mode="rectangle", size_hint_y=None, height=30)
            main_layout.add_widget(self.input_subtheme)
            main_layout.add_widget(Widget(size_hint_y=None, height=10)) 
            
            self.input_keywords = MDTextField(hint_text="Ключові слова", mode="rectangle", size_hint_y=None, height=30)
            main_layout.add_widget(self.input_keywords)
            main_layout.add_widget(Widget(size_hint_y=None, height=10)) 
            
            self.input_notes = MDTextField(hint_text="Нотатки / Короткий зміст ролика", mode="rectangle", multiline=True, size_hint_y=None, height=30)
            main_layout.add_widget(self.input_notes)
            
            main_layout.add_widget(Widget(size_hint_y=None, height=10))
            
            self.btn_add = MDRaisedButton(text="ЗБЕРЕГТИ В КАТАЛОГ", pos_hint={"center_x": .5}, size_hint_x=0.9, size_hint_y=None, height=38)
            self.btn_add.bind(on_release=self.process_add_video)
            main_layout.add_widget(self.btn_add)
            
            self.status_label = MDLabel(text="Каталог синхронізовано.", halign="center", theme_text_color="Secondary", size_hint_y=None, height=20)
            main_layout.add_widget(self.status_label)
            
            self.search_field = MDTextField(hint_text="🔍 Пошук по базі (назва, ключі, нотатки)...", mode="fill", size_hint_y=None, height=38)
            self.search_field.bind(text=self.on_search_text_change)
            main_layout.add_widget(self.search_field)
            
            scroll = MDScrollView(size_hint_y=1) 
            self.video_list = MDList(spacing=6)
            scroll.add_widget(self.video_list)
            main_layout.add_widget(scroll)
            
            self.add_widget(main_layout)
            self.load_data_from_base()

        def load_data_from_base(self):
            try:
                self.all_records = table.all()
                self.themes_set.clear()
                self.display_records(self.all_records)
                
                for record in self.all_records:
                    theme = record.get('fields', {}).get("Тема")
                    if theme: self.themes_set.add(theme)
                        
                self.update_theme_menu()
            except Exception as e:
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
                    orientation='horizontal', padding=6, spacing=12, size_hint_y=None, height=80, 
                    elevation=1, style="filled", md_bg_color=[0.15, 0.15, 0.15, 1]
                )
                
                thumb = ClickableThumbnail(source=img_url, size_hint_x=None, width=105, allow_stretch=True, keep_ratio=False)
                thumb.bind(on_release=lambda x, url=video_url: webbrowser.open(url))
                
                text_layout = MDBoxLayout(orientation='vertical', pos_hint={"center_y": .5})
                title_btn = MDFlatButton(
                    text=title if len(title) < 55 else f"{title[:52]}...",
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
            if not self.themes_set:
                return
            menu_items = [
                {"viewclass": "OneLineListItem", "text": theme, "on_release": lambda x=theme: self.set_theme(x)}
                for theme in sorted(list(self.themes_set))
            ]
            self.menu = MDDropdownMenu(caller=self.input_theme, items=menu_items, width_mult=4, max_height=200)

        def on_theme_field_click(self, instance, touch):
            if instance.collide_point(*touch.pos):
                if self.menu:  
                    self.menu.open()
                return True
            return False

        def set_theme(self, theme_text):
            self.input_theme.text = theme_text
            if self.menu:
                self.menu.dismiss()

        def process_add_video(self, instance):
            url = self.input_url.text.strip()
            theme = self.input_theme.text.strip()
            subtheme = self.input_subtheme.text.strip()
            keywords = self.input_keywords.text.strip()
            notes = self.input_notes.text.strip()
            
            if not url or not theme:
                return

            title, channel, thumbnail = extract_youtube_info(url)
            
            try:
                table.create({
                    "Посилання": url, "Назва відео": title, "Канал": channel,
                    "Тема": theme, "Підтема": subtheme, "Опис": thumbnail,
                    "Ключові слова": keywords, "Нотатки": notes
                })
                self.input_url.text = ""
                self.input_notes.text = ""
                self.load_data_from_base()
            except Exception as e:
                self.status_label.text = f"Помилка: {e}"

        def open_edit_dialog(self, record_id):
            self.current_edit_id = record_id
            target_fields = None
            for r in self.all_records:
                if r.get('id') == record_id:
                    target_fields = r.get('fields', {})
                    break
            if not target_fields: return
                
            self.edit_subtheme = MDTextField(text=target_fields.get('Підтема', ''), hint_text="Редагувати підтему", mode="rectangle")
            self.edit_keywords = MDTextField(text=target_fields.get('Ключові слова', ''), hint_text="Редагувати ключові слова", mode="rectangle")
            self.edit_notes = MDTextField(text=target_fields.get('Нотатки', ''), hint_text="Редагувати нотатки", mode="rectangle", multiline=True)
            
            dialog_layout = MDBoxLayout(orientation="vertical", spacing=10, size_hint_y=None, height=220)
            dialog_layout.add_widget(self.edit_subtheme)
            dialog_layout.add_widget(self.edit_keywords)
            dialog_layout.add_widget(self.edit_notes)
            
            self.dialog = MDDialog(
                title="📝 Виправлення даних ролика", type="custom", content_cls=dialog_layout,
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
            
            try:
                table.update(self.current_edit_id, {
                    "Підтема": new_subtheme, "Ключові слова": new_keywords, "Нотатки": new_notes
                })
                self.load_data_from_base()
            except Exception as e:
                self.status_label.text = f"Помилка: {e}"

        def delete_record(self, instance):
            self.dialog.dismiss()
            if not self.current_edit_id:
                return
                
            try:
                table.delete(self.current_edit_id)
                self.status_label.text = "Відео успішно видалено."
                self.load_data_from_base()
            except Exception as e:
                self.status_label.text = f"Помилка видалення: {e}"

    class YouTubeCatalogApp(MDApp):
        def build(self):
            self.theme_cls.primary_palette = "Blue"
            self.theme_cls.theme_style = "Dark"
            return MainScreen()

    if __name__ == '__main__':
        YouTubeCatalogApp().run()

except Exception as e:
    # ЯКЩО СТАЛАСЯ ПОМИЛКА, ВИВОДИМО ЇЇ НА ЕКРАН ТЕЛЕФОНУ
    from kivy.app import App
    from kivy.uix.label import Label
    from kivy.uix.scrollview import ScrollView
    from kivy.core.window import Window

    class CrashReporterApp(App):
        def build(self):
            Window.clearcolor = (0.1, 0.1, 0.1, 1)
            scroll = ScrollView(size_hint=(1, 1))
            error_text = f"ПОМИЛКА ЗАПУСКУ!\nСфотографуйте цей екран:\n\n{traceback.format_exc()}"
            
            label = Label(
                text=error_text,
                size_hint_y=None,
                font_size='14sp',
                halign='left',
                valign='top',
                color=(1, 0.2, 0.2, 1)
            )
            label.bind(
                width=lambda *x: label.setter('text_size')(label, (label.width - 40, None)),
                texture_size=lambda *x: label.setter('height')(label, label.texture_size[1] + 40)
            )
            scroll.add_widget(label)
            return scroll

    if __name__ == '__main__':
        CrashReporterApp().run()
