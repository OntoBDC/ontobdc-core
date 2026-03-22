


def print_logo():
    f = Figlet(font='big')
    ascii_art = f.renderText("My Desktop")
    title_text = Text(ascii_art.rstrip())