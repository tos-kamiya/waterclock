[→ English](README.md) → 日本語🇯🇵

Water Clock
===========

デジタルの水時計。

![](waterclock-screenshot4.png)

時計の数字の形の入れ物に水滴が落下・移動する様子がシミュレーションされます。  

オンライン版もあります → https://www.toshihirokamiya.com/waterclock/

## インストール

```sh
pipx install git+https://github.com/tos-kamiya/waterclock
```

または、

```sh
git clone https://github.com/tos-kamiya/waterclock
cd waterclock
pip install .
```

インストール後に、`waterclock` コマンドで起動してください。

## 利用法

デフォルトでは、PyQt5ベースのGUIで起動します。次のコマンドラインオプションが利用可能です。

- `--curses`  
  Cursesを利用してターミナルに描画します。

- `--pygame`  
  PygameをGUIフレームワークとして利用します。オプション `--acceleration` や `--add-hours` はPygameモードのときのみ利用可能です。

- `--theme {default,dark,light}`  
  カラーテーマを指定します。デフォルトは `default` です。

- `-g, --load-geometry`  
  起動時にウィンドウの位置とサイズを復元します。PyQt5モードのときのみ利用可能です。
