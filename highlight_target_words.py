from aqt import mw, Collection
from aqt.utils import tr, tooltip, qconnect
from aqt.browser import Browser
from aqt.operations import CollectionOp
from aqt.qt import QAction
from anki.hooks import addHook
import requests
from bs4 import BeautifulSoup
import re

config = mw.addonManager.getConfig(__name__)

EXPRESSION_FIELD = config["expressionField"]
READING_FIELD = config["readingField"]
SENTENCE_FIELD = config["sentenceField"]


def highlightTargetWords(col: Collection, nids: list[int]):
    undoEntry = col.add_custom_undo_entry("Highlight target words")
    notes = [mw.col.getNote(nid) for nid in nids]

    toUpdate = []
    for index, note in enumerate(notes):
        mw.taskman.run_on_main(
            lambda: mw.progress.update(
                label=f"{note[EXPRESSION_FIELD]} ({index}/{len(notes)})",
                value=index,
                max=len(notes)
            )
        )

        changed = highlightTargetWord(note)
        if changed:
            toUpdate.append(note)

    col.update_notes(toUpdate)
    return col.merge_undo_entries(undoEntry)


def highlightTargetWord(note):
    expression = note[EXPRESSION_FIELD]
    reading = note[READING_FIELD]
    sentence = note[SENTENCE_FIELD]
    if "<b>" in sentence:
        return False

    checks = [expression, hiraganaToKatakana(
        expression), reading, hiraganaToKatakana(reading)]

    for check in checks:
        if check in sentence:
            note[SENTENCE_FIELD] = sentence.replace(check, f"<b>{check}</b>")
            return True

    possibleForms = getPossibleForms(expression, sentence)
    for form in possibleForms:
        if form in sentence:
            if "<b>" in sentence:
                sentence = sentence.replace(
                    "</b>", "").replace(form, f"{form}</b>")
            else:
                sentence = sentence.replace(form, f"<b>{form}</b>")

    note[SENTENCE_FIELD] = sentence
    return "<b>" in sentence


def getPossibleForms(expression, sentence):
    url = f"https://ichi.moe/cl/qr/?q={sentence}&r=kana"
    forms = []

    response = requests.get(url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")

        pattern = r'[.0-9【】]'
        dtElements = soup.findAll(
            "dt", string=lambda s: expression in s or any(i in expression for i in re.sub(pattern, '', s).split()))
        for dtElement in dtElements:
            altDiv = dtElement.find_parent("dl", class_="alternatives")
            clozeDiv = altDiv.find("dt", recursive=False)
            cloze = clozeDiv.get_text()

            forms.extend(re.sub(pattern, '', cloze).split(" "))

    return forms


def hiraganaToKatakana(hiragana):
    return re.sub(r'[\u3041-\u3096]', lambda c: chr(ord(c.group(0)) + 0x60), hiragana)


def setupMenu(browser: Browser):
    action = QAction("Highlight target words", browser)
    qconnect(action.triggered, lambda: onHighlightTargetWords(
        nids=browser.selected_notes(), parent=browser))
    browser.form.menuEdit.addSeparator()
    browser.form.menuEdit.addAction(action)


def onHighlightTargetWords(nids: list[int], parent: Browser):
    op = CollectionOp(parent=parent, op=lambda col: highlightTargetWords(
        col, nids)).success(onSuccess)
    op.run_in_background()


def onSuccess(out):
    try:
        return tooltip(tr.browsing_notes_updated(count=out.count), parent=Browser)
    except:
        pass


addHook("browser.setupMenus", setupMenu)
