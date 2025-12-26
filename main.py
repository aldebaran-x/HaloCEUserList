#!/usr/bin/env python3

import os
import socket
import configparser

from kivy.app import App 
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import StringProperty, ListProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.label import Label

INI_FILE = "servers.ini"


# ------------------ Utils .INI ------------------

def load_servers():
    config = configparser.ConfigParser()
    if os.path.exists(INI_FILE):
        config.read(INI_FILE)
        return dict(config["Servers"]) if "Servers" in config else {}
    return {}


def parse_server_address(address):
    try:
        ip, port = address.split(":")
        return ip.strip(), int(port.strip())
    except Exception:
        return None, None


def save_server_logic(name, ip, port, confirm_fn, info_fn, warn_fn):
    """
    Same logic as your Tkinter version, but UI interactions are injected:
    - confirm_fn(title, message) -> bool
    - info_fn(title, message)
    - warn_fn(title, message)
    """
    if not name or not ip or not port:
        warn_fn("Champs manquants", "Veuillez remplir tous les champs.")
        return False

    config = configparser.ConfigParser()
    config.read(INI_FILE)

    if "Servers" not in config:
        config["Servers"] = {}

    ip_port_str = f"{ip}:{port}"
    existing_name = None

    # Vérifie si IP:PORT existe déjà sous un autre nom
    for n, addr in config["Servers"].items():
        if addr == ip_port_str:
            existing_name = n
            break

    # Cas 1 : IP déjà enregistrée sous le même nom → ne rien faire
    if existing_name == name:
        info_fn("Déjà enregistré", "Ce serveur est déjà enregistré sous ce nom.")
        return False

    # Cas 2 : IP existante mais nouveau nom → renommer
    if existing_name and existing_name != name:
        replace = confirm_fn(
            "Renommer le serveur",
            f"Ce serveur est déjà enregistré sous le nom '{existing_name}'.\n"
            f"Voulez-vous le renommer en '{name}' ?"
        )
        if replace:
            del config["Servers"][existing_name]
            config["Servers"][name] = ip_port_str
        else:
            return False

    # Cas 3 : Nouveau nom, nouvelle IP
    elif name in config["Servers"]:
        overwrite = confirm_fn("Nom existant", f"Remplacer le serveur existant '{name}' ?")
        if not overwrite:
            return False
        config["Servers"][name] = ip_port_str

    else:
        config["Servers"][name] = ip_port_str

    with open(INI_FILE, "w", encoding="utf-8") as f:
        config.write(f)

    info_fn("Serveur enregistré", f"Serveur '{name}' sauvegardé.")
    return True


# ------------------ Requête joueurs ------------------

def query_players(ip, port):
    """
    Same core query logic as your script, minus tkinter messageboxes.
    Raises exceptions to be handled by the UI layer (Kivy Popup).
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(2)

    request = b"\\players"
    s.sendto(request, (ip, int(port)))

    data, _ = s.recvfrom(8192)
    s.close()

    response = data.decode(errors='ignore').strip("\\").split("\\")
    response_dict = {response[i]: response[i + 1] for i in range(0, len(response) - 1, 2)}

    # Same special handling you had
    if "hostname" in response_dict and response_dict["hostname"]:
        try:
            if response_dict["hostname"][0] == 1:
                response_dict["hostname"] = response_dict.get("gamevariant", "")
        except Exception:
            pass

    game_info = {
        "hostname": response_dict.get("hostname", ""),
        "mapname": response_dict.get("mapname", ""),
        "gametype": response_dict.get("gametype", ""),
        "variant": response_dict.get("gamevariant", ""),
        "players": response_dict.get("numplayers", ""),
        "maxplayers": response_dict.get("maxplayers", "")
    }

    teams = {
        "0": response_dict.get("team_t0", "Red") or "Red",
        "1": response_dict.get("team_t1", "Blue") or "Blue"
    }

    players = []
    index = 0
    while True:
        name_key = f"player_{index}"
        if name_key not in response_dict:
            break

        team_id = response_dict.get(f"team_{index}", "")
        team_name = teams.get(team_id, "Inconnue")

        player = {
            "name": response_dict.get(name_key, ""),
            "score": response_dict.get(f"score_{index}", ""),
            "ping": response_dict.get(f"ping_{index}", ""),
            "team": team_name
        }
        players.append(player)
        index += 1

    players.sort(key=lambda p: p.get("team", ""))
    return players, game_info


# ------------------ UI (Kivy) ------------------

KV = r"""
<PlayerRow>:
    # Force black text for readability
    orientation: "horizontal"
    size_hint_y: None
    height: dp(28)
    canvas.before:
        Color:
            rgba: root.bg_rgba
        Rectangle:
            pos: self.pos
            size: self.size

    Label:
        color: 0, 0, 0, 1
        text: root.name
        halign: "left"
        valign: "middle"
        text_size: self.size
    Label:
        color: 0, 0, 0, 1
        text: root.score
        halign: "center"
        valign: "middle"
        text_size: self.size
        size_hint_x: 0.25
    Label:
        color: 0, 0, 0, 1
        text: root.ping
        halign: "center"
        valign: "middle"
        text_size: self.size
        size_hint_x: 0.25
    Label:
        color: 0, 0, 0, 1
        text: root.team
        halign: "left"
        valign: "middle"
        text_size: self.size
        size_hint_x: 0.35

<RootUI>:
    orientation: "vertical"
    padding: dp(10)
    spacing: dp(8)

    BoxLayout:
        size_hint_y: None
        height: dp(32)
        spacing: dp(8)

        Label:
            text: "Choisir un serveur enregistré :"
            size_hint_x: 0.45
            halign: "right"
            valign: "middle"
            text_size: self.size

        Spinner:
            id: server_spinner
            text: root.server_selected_text
            values: root.server_names
            size_hint_x: 0.55
            on_text: root.on_server_selected(self.text)

    BoxLayout:
        size_hint_y: None
        height: dp(32)
        spacing: dp(8)

        Label:
            text: "Adresse IP:"
            size_hint_x: 0.2
            halign: "right"
            valign: "middle"
            text_size: self.size

        TextInput:
            id: ip_input
            multiline: False
            write_tab: False
            hint_text: "ex: 127.0.0.1"
            size_hint_x: 0.45

        Label:
            text: "Port:"
            size_hint_x: 0.1
            halign: "right"
            valign: "middle"
            text_size: self.size

        TextInput:
            id: port_input
            multiline: False
            write_tab: False
            hint_text: "ex: 2302"
            input_filter: "int"
            size_hint_x: 0.25

    Button:
        text: "Obtenir la liste des joueurs"
        size_hint_y: None
        height: dp(40)
        on_release: root.display_players()

    BoxLayout:
        size_hint_y: None
        height: dp(32)
        spacing: dp(8)

        Label:
            text: "Nom du serveur :"
            size_hint_x: 0.25
            halign: "right"
            valign: "middle"
            text_size: self.size

        TextInput:
            id: name_input
            multiline: False
            write_tab: False
            size_hint_x: 0.5

        Button:
            text: "Ajouter le serveur"
            size_hint_x: 0.25
            on_release: root.add_server()

    Label:
        id: game_info
        text: root.game_info_text
        size_hint_y: None
        height: dp(26)

    BoxLayout:
        size_hint_y: None
        height: dp(28)
        canvas.before:
            Color:
                rgba: 0.15, 0.15, 0.15, 1
            Rectangle:
                pos: self.pos
                size: self.size

        Label:
            text: "Nom"
            bold: True
        Label:
            text: "Score"
            bold: True
            size_hint_x: 0.25
        Label:
            text: "Ping"
            bold: True
            size_hint_x: 0.25
        Label:
            text: "Équipe"
            bold: True
            size_hint_x: 0.35

    ScrollView:
        do_scroll_x: False

        GridLayout:
            id: players_grid
            cols: 1
            size_hint_y: None
            height: self.minimum_height
            spacing: dp(2)
"""

class PlayerRow(BoxLayout):
    # Use Kivy Properties so KV bindings update properly
    name = StringProperty("")
    score = StringProperty("")
    ping = StringProperty("")
    team = StringProperty("")
    bg_rgba = ListProperty([0.93, 0.93, 0.93, 1.0])


class RootUI(BoxLayout):
    server_selected_text = StringProperty("—")
    game_info_text = StringProperty("")
    # we store list values dynamically:
    server_names = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.saved_servers = {}
        self.refresh_server_list()

    # ---------- Popups ----------
    def _popup(self, title, message):
        content = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))
        content.add_widget(Label(text=message, halign="left", valign="middle"))
        btn = Label(text="[ref=close]OK[/ref]", markup=True, size_hint_y=None, height=dp(30))
        content.add_widget(btn)

        popup = Popup(title=title, content=content, size_hint=(0.7, 0.35), auto_dismiss=False)

        def close_cb(*_):
            popup.dismiss()

        btn.bind(on_ref_press=lambda *_: close_cb())
        popup.open()

    def info(self, title, message):
        self._popup(title, message)

    def warn(self, title, message):
        self._popup(title, message)

    def error(self, title, message):
        self._popup(title, message)

    def confirm(self, title, message, on_result):
        """
        Async confirm dialog: calls on_result(True/False).
        """
        content = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))
        content.add_widget(Label(text=message, halign="left", valign="middle"))

        buttons = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(10))
        from kivy.uix.button import Button
        yes_btn = Button(text="Oui")
        no_btn = Button(text="Non")
        buttons.add_widget(yes_btn)
        buttons.add_widget(no_btn)
        content.add_widget(buttons)

        popup = Popup(title=title, content=content, size_hint=(0.75, 0.4), auto_dismiss=False)

        def choose(val):
            popup.dismiss()
            on_result(val)

        yes_btn.bind(on_release=lambda *_: choose(True))
        no_btn.bind(on_release=lambda *_: choose(False))
        popup.open()

    # ---------- Server list ----------
    def refresh_server_list(self):
        self.saved_servers = load_servers()
        self.server_names = list(self.saved_servers.keys())
        # Update spinner values (if UI already built)
        if self.ids.get("server_spinner"):
            self.ids.server_spinner.values = self.server_names
        if self.server_selected_text != "—" and self.server_selected_text not in self.saved_servers:
            self.server_selected_text = "—"

    def on_server_selected(self, selected_name):
        self.server_selected_text = selected_name
        if selected_name in self.saved_servers:
            ip, port = parse_server_address(self.saved_servers[selected_name])
            if ip and port:
                self.ids.ip_input.text = ip
                self.ids.port_input.text = str(port)
                # Match original behavior: auto-query on selection
                # Run next frame to ensure UI updates are visible
                Clock.schedule_once(lambda *_: self.display_players(), 0)

    # ---------- Players display ----------
    def clear_players(self):
        grid = self.ids.players_grid
        grid.clear_widgets()

    def _team_bg_rgba(self, team_name):
        t = (team_name or "").strip().lower()
        if t == "red":
            return (1.0, 0.87, 0.87, 1.0)  # #ffdddd-ish
        if t == "blue":
            return (0.87, 0.87, 1.0, 1.0)  # #ddddff-ish
        return (0.93, 0.93, 0.93, 1.0)      # #eeeeee-ish

    def display_players(self):
        ip = self.ids.ip_input.text.strip()
        port = self.ids.port_input.text.strip()

        self.clear_players()

        if not ip or not port:
            self.warn("Champ vide", "Veuillez entrer l'adresse IP et le port.")
            return

        try:
            players, info = query_players(ip, port)
        except Exception as e:
            self.error("Erreur", str(e))
            self.game_info_text = ""
            return

        hostname = (info.get("hostname", "") or "").strip()

        # Same “control-char” workaround you had
        if hostname:
            try:
                if ord(hostname[0]) < 30:
                    hostname = self.server_selected_text if self.server_selected_text != "—" else hostname
            except Exception:
                pass

        # Update "Nom du serveur" field with hostname
        if hostname:
            self.ids.name_input.text = hostname

        # Fill players
        grid = self.ids.players_grid
        for p in players:
            team = p.get("team", "") or ""
            row = PlayerRow()
            row.name = str(p.get("name", ""))
            row.score = str(p.get("score", ""))
            row.ping = str(p.get("ping", ""))
            row.team = str(team)
            row.bg_rgba = self._team_bg_rgba(team)
            grid.add_widget(row)

        self.game_info_text = (
            f"🎮 {hostname} | Map: {info.get('mapname')} | "
            f"Type: {info.get('gametype')} ({info.get('variant')}) | "
            f"Joueurs: {info.get('players')}/{info.get('maxplayers')}"
        )

    # ---------- Add/Save server ----------
    def add_server(self):
        name = self.ids.name_input.text.strip()
        ip = self.ids.ip_input.text.strip()
        port = self.ids.port_input.text.strip()

        # Kivy confirm popups are async, so we wrap the save logic
        def do_save():
            def confirm_fn(title, message):
                # We'll convert sync-style to async by blocking via callback pattern:
                # Instead of blocking, we return None and handle with callback below.
                raise RuntimeError("confirm_fn should not be called directly in async mode")

            # We can't use the sync logic directly for confirms; so we implement the same branches here:
            config = configparser.ConfigParser()
            config.read(INI_FILE)
            if "Servers" not in config:
                config["Servers"] = {}

            if not name or not ip or not port:
                self.warn("Champs manquants", "Veuillez remplir tous les champs.")
                return

            ip_port_str = f"{ip}:{port}"

            existing_name = None
            for n, addr in config["Servers"].items():
                if addr == ip_port_str:
                    existing_name = n
                    break

            if existing_name == name:
                self.info("Déjà enregistré", "Ce serveur est déjà enregistré sous ce nom.")
                return

            def write_and_refresh():
                with open(INI_FILE, "w", encoding="utf-8") as f:
                    config.write(f)
                self.info("Serveur enregistré", f"Serveur '{name}' sauvegardé.")
                self.refresh_server_list()

            # Case: same IP/PORT under different name -> confirm rename
            if existing_name and existing_name != name:
                def after_rename(ok):
                    if not ok:
                        return
                    del config["Servers"][existing_name]
                    config["Servers"][name] = ip_port_str
                    write_and_refresh()

                self.confirm(
                    "Renommer le serveur",
                    f"Ce serveur est déjà enregistré sous le nom '{existing_name}'.\n"
                    f"Voulez-vous le renommer en '{name}' ?",
                    after_rename
                )
                return

            # Case: name exists -> confirm overwrite
            if name in config["Servers"]:
                def after_overwrite(ok):
                    if not ok:
                        return
                    config["Servers"][name] = ip_port_str
                    write_and_refresh()

                self.confirm("Nom existant", f"Remplacer le serveur existant '{name}' ?", after_overwrite)
                return

            # New name + new IP
            config["Servers"][name] = ip_port_str
            write_and_refresh()

        do_save()


class HaloCEPlayersApp(App):
    def build(self):
        self.title = "HaloCE - Liste des joueurs"
        Builder.load_string(KV)
        # Optional: set a reasonable default size for desktop
        Window.minimum_width = 900
        Window.minimum_height = 600
        return RootUI()


if __name__ == "__main__":
    HaloCEPlayersApp().run()

