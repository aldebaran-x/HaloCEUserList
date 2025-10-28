import socket
import tkinter as tk
from tkinter import messagebox, ttk
import configparser
import os

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
    except:
        return None, None

def refresh_server_list():
    global saved_servers
    saved_servers = load_servers()
    server_menu["values"] = list(saved_servers.keys())

def save_server(name, ip, port):
    global saved_servers
    if not name or not ip or not port:
        messagebox.showwarning("Champs manquants", "Veuillez remplir tous les champs.")
        return

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
        messagebox.showinfo("Déjà enregistré", f"Ce serveur est déjà enregistré sous ce nom.")
        return

    # Cas 2 : IP existante mais nouveau nom → renommer
    if existing_name and existing_name != name:
        replace = messagebox.askyesno(
            "Renommer le serveur",
            f"Ce serveur est déjà enregistré sous le nom '{existing_name}'.\n"
            f"Voulez-vous le renommer en '{name}' ?"
        )
        if replace:
            del config["Servers"][existing_name]
            config["Servers"][name] = ip_port_str
        else:
            return

    # Cas 3 : Nouveau nom, nouvelle IP
    elif name in config["Servers"]:
        overwrite = messagebox.askyesno("Nom existant", f"Remplacer le serveur existant '{name}' ?")
        if not overwrite:
            return
        config["Servers"][name] = ip_port_str

    else:
        config["Servers"][name] = ip_port_str

    with open(INI_FILE, "w", encoding="utf-8") as f:
        config.write(f)

    messagebox.showinfo("Serveur enregistré", f"Serveur '{name}' sauvegardé.")
    refresh_server_list()


# ------------------ Requête joueurs ------------------

def query_players(ip, port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)

        request = b"\\players\\final\\"
        s.sendto(request, (ip, int(port)))

        data, _ = s.recvfrom(4096)
        s.close()
        print('raw:')
        print(data, flush=True)
        print('--')
        response = data.decode(errors='ignore').strip("\\").split("\\")
        print(response, flush=True)
        response_dict = {response[i]: response[i + 1] for i in range(0, len(response) - 1, 2)}
        print('--')
        print(response_dict, flush=True)
        if response_dict["hostname"][0] == 1:
            print("error", flush=True)
            response_dict["hostname"] = response_dict.get("gamevariant", "")

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
        print(teams, flush=True)

        players = []
        index = 0
        while True:
            name_key = f"player_{index}"
            if name_key not in response_dict:
                break
            team_id = response_dict.get(f"team_{index}", "")
            print(team_id, flush=True)
            team_name = teams.get(team_id, "Inconnue")
            print(team_name, flush=True)

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

    except Exception as e:
        messagebox.showerror("Erreur", str(e))
        return [], {}

# ------------------ Affichage GUI ------------------

def display_players():
    ip = ip_entry.get()
    port = port_entry.get()

    for row in tree.get_children():
        tree.delete(row)

    if not ip or not port:
        messagebox.showwarning("Champ vide", "Veuillez entrer l'adresse IP et le port.")
        return

    players, info = query_players(ip, port)

    # Met à jour le champ "Nom du serveur" avec le hostname
    hostname = info.get("hostname", "").strip()
    if ord(hostname[0]) < 30:
        hostname = server_var.get()
    if hostname:
        name_entry.delete(0, tk.END)
        name_entry.insert(0, hostname)

    print ("Players:")
    print (players, flush=True)
    for p in players:
        team = p.get("team", "")
        color = "#eeeeee"
        if team.lower() == "red":
            color = "#ffdddd"
        elif team.lower() == "blue":
            color = "#ddddff"

        tree.insert("", "end", values=(p["name"], p["score"], p["ping"], team), tags=(team,))
        tree.tag_configure(team, background=color)

    game_info_label.config(
        text=f"🎮 {hostname} | Map: {info.get('mapname')} | "
             f"Type: {info.get('gametype')} ({info.get('variant')}) | Joueurs: {info.get('players')}/{info.get('maxplayers')}"
    )

def on_server_selected(event=None):
    selected = server_var.get()
    if selected in saved_servers:
        ip, port = parse_server_address(saved_servers[selected])
        if ip and port:
            ip_entry.delete(0, tk.END)
            port_entry.delete(0, tk.END)
            ip_entry.insert(0, ip)
            port_entry.insert(0, str(port))
            display_players()

# ------------------ Fenêtre principale ------------------

root = tk.Tk()
root.title("HaloCE - Liste des joueurs")

frame = tk.Frame(root, padx=10, pady=10)
frame.pack()

tk.Label(frame, text="Choisir un serveur enregistré :").grid(row=0, column=0, sticky="e")
server_var = tk.StringVar()
server_menu = ttk.Combobox(frame, textvariable=server_var, state="readonly", width=30)
server_menu.grid(row=0, column=1, columnspan=2, pady=5)
server_menu.bind("<<ComboboxSelected>>", on_server_selected)

tk.Label(frame, text="Adresse IP:").grid(row=1, column=0, sticky="e")
ip_entry = tk.Entry(frame)
ip_entry.grid(row=1, column=1)

tk.Label(frame, text="Port:").grid(row=1, column=2, sticky="e")
port_entry = tk.Entry(frame)
port_entry.grid(row=1, column=3)

query_button = tk.Button(frame, text="Obtenir la liste des joueurs", command=display_players)
query_button.grid(row=2, column=0, columnspan=4, pady=10)

tk.Label(frame, text="Nom du serveur :").grid(row=3, column=0, sticky="e")
name_entry = tk.Entry(frame)
name_entry.grid(row=3, column=1, columnspan=2, sticky="we")

add_button = tk.Button(frame, text="Ajouter le serveur", command=lambda: save_server(
    name_entry.get(), ip_entry.get(), port_entry.get()))
add_button.grid(row=3, column=3, sticky="we", pady=5)

game_info_label = tk.Label(root, text="", font=("Helvetica", 10), fg="blue")
game_info_label.pack()

tree = ttk.Treeview(root, columns=("Nom", "Score", "Ping", "Équipe"), show="headings", height=17)

tree.heading("Nom", text="Nom")
tree.heading("Score", text="Score")
tree.heading("Ping", text="Ping")
tree.heading("Équipe", text="Équipe")
tree.pack(padx=10, pady=10)

# Charger les serveurs
saved_servers = load_servers()
server_menu["values"] = list(saved_servers.keys())

root.mainloop()

