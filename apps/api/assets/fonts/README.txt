NotoSansVN-Regular.ttf
  Noto Sans Regular (Copyright 2015-2021 Google LLC) — SIL Open Font License 1.1 (https://openfontlicense.org/)
  を、ラテン文字・ベトナム語(U+0020-024F, U+1EA0-1EF9 ほか)だけに絞った版(約65KB)。
  元のフォントをそのまま pdf-lib(fontkit) で subset すると字形が欠けるため、事前に絞ってある。
  用途: 段取シートPDF/HTMLのベトナム語表示。日本語は従来どおり IPAゴシック
        (/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf)を使う。
  作り方: pyftsubset NotoSans-Regular.ttf --unicodes="U+0020-007E,U+00A0-017F,U+0180-024F,U+02B0-02FF,U+0300-036F,U+1EA0-1EF9,U+2010-2027,U+2030-203A,U+20AB,U+20AC,U+2190-2193,U+2212,U+25A0-25CF" --layout-features=kern --no-hinting --notdef-outline
