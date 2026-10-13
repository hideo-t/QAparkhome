"""公式サイト（phoka2）の日本語ページから、AIアシスタント用の知識ベース kb.json を作る。

使い方: python -I kb/build_kb.py <phoka2のパス> [出力先 kb/kb.json]

- 対象ページは phoka2 の sitemap.xml に載っている日本語URL（実際に公開しているページ）
- メニュー・フッター・スクリプト等を除き、見出しと本文だけを残す
- 1ページ1件。出典URLと更新日（そのファイルの最終コミット日）を付ける
- 社内作成の一般Q&A（base_qa_50.json）も「一般的な解説」として入れる
設計: docs/rag/DESIGN.md
"""
import json, re, subprocess, sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

SITE = "https://parkhomes-okinawa.com"
EXCLUDE = {"/sitemap/", "/j/privacy/", "/contact/thanks.html", "/pages/estimate.html", "/pages/amalfi-gallery.html"}
SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "button", "template"}
SKIP_CLASSES = {"mobile-menu", "hamburger", "nav-links", "nav-inner", "pkw-langbar", "breadcrumb"}
VOID = {"br", "img", "hr", "meta", "link", "input", "source", "area", "base", "col", "embed", "wbr", "track", "param"}
# 全ページに出るメニュー・ボタンの文言（本文ではない）
NOISE = re.compile(r"^(🤖 ?AI相談|💬 ?LINE|📋 ?見積もり|トップへ|TOP注目される3つの特徴|無料で相談する →|お問い合わせ・見積もり →)")
BLOCK = {"p", "div", "section", "article", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "dt", "dd", "table", "ul", "ol", "dl", "br", "blockquote", "figcaption"}


class Extract(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []      # 開いている要素ごとに (タグ名, スキップするか)
        self.out = []
        self.title = ""
        self.h1 = ""
        self._in = None      # title / h1 の文字を拾う
        self.desc = ""

    def skipping(self):
        return any(skip for _, skip in self.stack)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta" and a.get("name") == "description":
            self.desc = a.get("content", "")
        if tag in VOID:
            if tag == "br" and not self.skipping():
                self.out.append("\n")
            return
        classes = set((a.get("class") or "").split())
        skip = tag in SKIP_TAGS or bool(classes & SKIP_CLASSES) or any(c.startswith("footer") for c in classes)
        self.stack.append((tag, skip))
        if self.skipping():
            return
        if tag == "title" or (tag == "h1" and not self.h1):
            self._in = tag
        if tag in BLOCK:
            self.out.append("\n")
        if re.fullmatch(r"h[1-4]", tag):
            self.out.append("#" * int(tag[1]) + " ")
        elif tag == "li":
            self.out.append("- ")

    def handle_endtag(self, tag):
        # 閉じタグの省略（<li> 等）や余分な閉じタグがあってもずれないよう、同じ名前の要素まで戻す
        if tag in VOID or not any(t == tag for t, _ in self.stack):
            return
        if tag in BLOCK and not self.skipping():
            self.out.append("\n")
        if self._in == tag:
            self._in = None
        while self.stack:
            if self.stack.pop()[0] == tag:
                break

    def handle_data(self, data):
        if self._in == "title":
            self.title += data
            return
        if self.skipping():
            return
        if self._in == "h1":
            self.h1 += data
        self.out.append(data)

    def text(self):
        t = "".join(self.out)
        lines = [re.sub(r"[ \t　]+", " ", l).strip() for l in t.split("\n")]
        lines = [l for l in lines if l and l not in ("-", "#", "##", "###", "####") and not NOISE.search(l)]
        # 他社サイトのURLは載せない（回答の参考リンクは公式サイトだけにする）
        lines = [re.sub(r"https?://(?!(www\.)?parkhomes-okinawa\.com)\S+", "", l).strip() for l in lines]
        lines = [re.sub(r"  +", " ", l) for l in lines if l]
        # 直前と同じ行の繰り返しを除く
        out = []
        for l in lines:
            if not out or out[-1] != l:
                out.append(l)
        return "\n".join(out)


def page_file(root: Path, path: str) -> Path:
    p = unquote(path)
    f = root / p.lstrip("/")
    return f / "index.html" if p.endswith("/") else f


def last_commit_date(root: Path, f: Path) -> str:
    r = subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%cs", "--", str(f.relative_to(root))],
                       capture_output=True, text=True, encoding="utf-8")
    return r.stdout.strip()


def main():
    root = Path(sys.argv[1])
    out = Path(sys.argv[2] if len(sys.argv) > 2 else Path(__file__).with_name("kb.json"))
    sitemap = (root / "sitemap.xml").read_text(encoding="utf-8")
    urls = [u for u in re.findall(r"<loc>([^<]+)</loc>", sitemap)
            if not re.search(r"/(en|ko|zh-Hans|zh-Hant)/", u)]

    docs = []
    for u in urls:
        path = urlparse(u).path or "/"
        if unquote(path) in EXCLUDE:
            continue
        f = page_file(root, path)
        if not f.exists():
            print("見つからない:", unquote(path), file=sys.stderr)
            continue
        ex = Extract()
        ex.feed(f.read_text(encoding="utf-8"))
        ex.close()
        if any(skip for _, skip in ex.stack):
            print("警告: スキップ中のまま終わった:", unquote(path), file=sys.stderr)
        title = (ex.h1 or ex.title.split(" - ")[0].split("｜")[0].split("|")[0]).strip()
        body = ex.text()
        if ex.desc and ex.desc not in body:
            body = ex.desc + "\n" + body
        if "</doc>" in body or len(body) < 80:
            print(f"警告: 本文を確認してください（{len(body)}字）:", unquote(path), file=sys.stderr)
        docs.append({"id": f"S{len(docs) + 1:02d}", "kind": "site", "title": title,
                     "url": SITE + unquote(path), "updated": last_commit_date(root, f), "text": body})

    qa = json.loads((Path(__file__).resolve().parents[1] / "base_qa_50.json").read_text(encoding="utf-8"))
    for i, x in enumerate(qa, 1):
        docs.append({"id": f"G{i:02d}", "kind": "general", "title": x["question"], "category": x["category"],
                     "url": None, "updated": None, "text": x["answer"]})

    out.write_text(json.dumps(docs, ensure_ascii=False, indent=1), encoding="utf-8")
    site = [d for d in docs if d["kind"] == "site"]
    print(f"site {len(site)}件 / general {len(docs) - len(site)}件 / 本文 {sum(len(d['text']) for d in docs):,}字 → {out}")


if __name__ == "__main__":
    main()
