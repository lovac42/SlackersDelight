# -*- coding: utf-8 -*-
# Copyright: (C) 2018 Lovac42
# Support: https://github.com/lovac42/SlackersDelight
# License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html
# Version: 0.0.1


# == User Config =========================================

HOTKEY = "_" #Shift + Bury

#Warning: Abuse addiction, disable and use menu
ADD_DEFER_BUTTON = True

DEFERRED_DECK_NAME = "~Slackers Postponed Delights~"

# == End Config ==========================================
##########################################################


import aqt, time
import anki.sched
from aqt import mw
from aqt.qt import *
from aqt.reviewer import Reviewer
from anki.hooks import addHook, wrap
from anki.utils import intTime
from aqt.utils import showWarning, showInfo, tooltip
from anki import version
ANKI21 = version.startswith("2.1.")


DEFERRED_DECK_DESC = """
<p><i>This is a deck full of deferred
 cards for slackers.</i></p><p>
<b>Warning:</b> On mobile, or without this addon,<br>
learning cards are converted to review or new cards<br>
when the empty button is clicked.<br>
<i>(Default behavior on the V1 Scheduler,<br>
not a problem on the V2 Scheduler.)</i></p><br>"""


class SlackersDelight:
    def __init__(self):
        self.timeId=intTime()%100000
        addHook("Reviewer.contextMenuEvent", self.showContextMenu)

    def showContextMenu(self, r, m):
        if r.card.odid: return
        a=m.addAction("Defer")
        a.setShortcut(QKeySequence(HOTKEY))
        a.triggered.connect(self.defer)

    def defer(self):
        "main operations"
        card = mw.reviewer.card
        if card.odid: return
        did = self.getDynId()
        if did:
            mw.col.log(did,[card.id])
            self.swap(did, card)
            mw.reset()
            tooltip(_("Card Deferred."), period=1000)

    def getDynId(self):
        "Built or select Dyn deck"
        dyn=mw.col.decks.byName(_(DEFERRED_DECK_NAME))
        if not dyn: #Create filtered deck
            did =  mw.col.decks.id(_(DEFERRED_DECK_NAME), 
                        type=anki.decks.defaultDynamicDeck)
            dyn = mw.col.decks.get(did)
        elif not dyn['dyn']: #Regular deck w/ same name
            showInfo("Please rename the existing %s deck first."%DEFERRED_DECK_NAME)
            return False
        return dyn['id']

    def swap(self, dynId, card):
        "Swap card info"
        card.odid=card.did
        card.did=dynId
        if card.queue in (1,3) and mw.col.sched.name != "std2":
            #fix bad cards during db check
            card.odue=mw.col.sched.today
        else: #new/rev cards
            card.odue=card.due
            card.due=-self.timeId
            self.timeId+=1
        card.flush()


sd=SlackersDelight()


##########################################################
# ALL MONKEY PATCH CR..Stuff BELOW #######################

#Friendly Warning Message
def desc(self, deck, _old):
    if deck['name'] != DEFERRED_DECK_NAME:
        return _old(self, deck)
    return DEFERRED_DECK_DESC


#Handing keybinds Anki2.0
def keyHandler(self, evt, _old):
    if unicode(evt.text()) == HOTKEY:
        sd.defer()
    else: _old(self, evt)

#Handing keybinds Anki2.1
def shortcutKeys(self, _old): 
    ret=_old(self)
    ret.append((HOTKEY, sd.defer))
    return ret


#Add button on bottom bar
def initWeb(self):
    card = mw.reviewer.card
    conf = mw.col.decks.confForDid(card.did)
    if conf['dyn']: return
    lnkcmd="pycmd" if ANKI21 else "py.link"
    dbtn = """<td width="50" align="right" valign="top" class="stat"><br><button title="Shortcut key: _" id="defbut" onclick="%s(&quot;deferbtn&quot;);">Defer</button></td>"""%lnkcmd
    self.bottom.web.eval("""$("#middle")[0].outerHTML+='%s';"""%dbtn)

#handles callback from button
def linkHandler(self, url, _old):
    if url == "deferbtn": sd.defer()
    else: _old(self, url)


#For V1 Scheduler:
#This is necessary to keep the learning card status if user clicks empty.
#Default is to change type1=0 new, type2=2 review
def sd_emptyDyn(self, did, lim=None, _old=None):
    if not _old: _old=lim; lim=None; #swap
    dyn = mw.col.decks.get(did)
    if dyn['name'] != DEFERRED_DECK_NAME:
        return _old(self, did, lim)
    if not lim:
        lim = "did = %s" % did
    self.col.log(self.col.db.list("select id from cards where %s" % lim))
    self.col.db.execute("""
update cards set did = odid,
due = (case when queue in (1,3) then due else odue end),
odue = 0, odid = 0, usn = ? where %s""" %
lim, self.col.usn())


#Prevent user from rebuilding this special deck
def sd_rebuildDyn(self, did=None, _old=None):
    if not _old: _old=did; did=None; #swap
    did = did or self.col.decks.selected()
    dyn = mw.col.decks.get(did)
    if dyn['name'] == DEFERRED_DECK_NAME:
        showWarning("Can't modify this deck.") 
        return None
    return _old(self, did)


#Prevent user from changing deck options
def sd_onDeckConf(self, deck=None):
    if not deck:
        deck = self.col.decks.current()
    if deck['name'] == DEFERRED_DECK_NAME:
        showWarning("Can't modify this deck.") 
        return
    return old_onDeckConf(self, deck)

old_onDeckConf=aqt.main.AnkiQt.onDeckConf
aqt.main.AnkiQt.onDeckConf=sd_onDeckConf

if ADD_DEFER_BUTTON:
    Reviewer._initWeb = wrap(Reviewer._initWeb, initWeb, 'after')
    Reviewer._linkHandler = wrap(Reviewer._linkHandler, linkHandler, 'around')

aqt.overview.Overview._desc = wrap(aqt.overview.Overview._desc, desc, 'around')
anki.sched.Scheduler.emptyDyn = wrap(anki.sched.Scheduler.emptyDyn, sd_emptyDyn, 'around')
anki.sched.Scheduler.rebuildDyn = wrap(anki.sched.Scheduler.rebuildDyn, sd_rebuildDyn, 'around')

if ANKI21:
    import anki.schedv2
    anki.schedv2.Scheduler.rebuildDyn = wrap(anki.schedv2.Scheduler.rebuildDyn, sd_rebuildDyn, 'around')
    Reviewer._shortcutKeys = wrap(Reviewer._shortcutKeys, shortcutKeys, 'around')
else:
    Reviewer._keyHandler = wrap(Reviewer._keyHandler, keyHandler, 'around')
