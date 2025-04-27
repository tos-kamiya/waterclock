→ English [→ 日本語🇯🇵](README-ja_JP.md)

# Water Clock

A digital water clock.

![](waterclock-screenshot5.png)

This project simulates water droplets falling and moving inside containers shaped like digital clock digits.

## Installation

Using pipx:

```sh
pipx install git+https://github.com/tos-kamiya/waterclock
```

Or, clone and install:

```sh
git clone https://github.com/tos-kamiya/waterclock
cd waterclock
pip install .
```

After installation, launch the clock with the `waterclock` command.

## Usage

By default, the application starts with a PyQt5-based GUI. The following command-line options are available:

- `--curses`  
  Use curses for terminal rendering.

- `--pygame`  
  Use Pygame as the GUI framework. Note that options `--acceleration` and `--add-hours` are only valid with Pygame.

- `--theme {default,dark,light}`  
  Set the color theme. Defaults to `default`.

- `-g, --load-geometry`  
  Restore window position and size on startup (only valid with the default PyQt5 mode).

- `--no-taskbar-icon`  
  Hide taskbar icon (only valid with the default PyQt5 mode).
