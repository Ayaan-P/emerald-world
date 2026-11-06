"""Persistent, non-binding player trade advertisements.

The authenticated World authority supplies trainer identities. Listings are
unverified descriptions: no Pokémon, items, money, saves or trade approvals
are read or transferred. Actual trades use the game's existing consent flow.
"""
import re
import time

NAME=re.compile(r'[A-Za-z0-9_-]{1,24}\Z')
TTL=7*24*60*60
MAX_LISTINGS=512

class TradeBoardError(ValueError):
    pass

class TradeBoard:
    def __init__(self,db,clock=time.time):
        self.db=db;self.clock=clock
        db.execute('''CREATE TABLE IF NOT EXISTS trade_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT, trainer TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL, expires INTEGER NOT NULL)''')
        db.commit()

    def _now(self):return int(self.clock())

    def _prune(self,now):self.db.execute('DELETE FROM trade_listings WHERE expires<=?',(now,))

    def command(self,trainer,text):
        if not isinstance(trainer,str) or not NAME.fullmatch(trainer):raise TradeBoardError('Invalid trainer.')
        if not isinstance(text,str) or len(text)>120:raise TradeBoardError('Invalid trade board command.')
        words=text.split();op=words[0].lower() if words else 'help';args=words[1:];now=self._now()
        with self.db:
            self._prune(now)
            if op=='help' and not args:
                return ['protocol 1','/trade offer DESCRIPTION | /trade mine | /trade remove',
                        '/trade list [PAGE] | /trade contact LISTING_ID',
                        'Listings are public and unverified. Use the normal game trade flow.']
            if op=='offer':
                description=text[len(words[0]):].strip()
                if not 1<=len(description)<=60 or not description.isascii() or any(ord(c)<32 or ord(c)>126 for c in description):
                    raise TradeBoardError('Use /trade offer followed by 1-60 printable characters.')
                if self.db.execute('SELECT 1 FROM trade_listings WHERE trainer=?',(trainer,)).fetchone():
                    raise TradeBoardError('Remove your existing listing first.')
                if self.db.execute('SELECT COUNT(*) FROM trade_listings').fetchone()[0]>=MAX_LISTINGS:
                    raise TradeBoardError('Trade board is full. Try again later.')
                cur=self.db.execute('INSERT INTO trade_listings(trainer,description,expires) VALUES(?,?,?)',(trainer,description,now+TTL))
                return [f'Posted listing {cur.lastrowid}. It expires in 7 days.']
            if op=='remove' and not args:
                removed=self.db.execute('DELETE FROM trade_listings WHERE trainer=?',(trainer,)).rowcount
                return ['Listing removed.' if removed else 'You have no active listing.']
            if op=='mine' and not args:
                row=self.db.execute('SELECT id,description FROM trade_listings WHERE trainer=?',(trainer,)).fetchone()
                return [f'{row[0]} {trainer}: {row[1]}'] if row else ['You have no active listing.']
            if op=='list':
                if len(args)>1 or (args and (not args[0].isascii() or not args[0].isdecimal() or len(args[0])>3)):
                    raise TradeBoardError('Use /trade list or /trade list PAGE.')
                page=int(args[0]) if args else 1;total=self.db.execute('SELECT COUNT(*) FROM trade_listings').fetchone()[0]
                pages=max(1,(total+7)//8)
                if not 1<=page<=pages:raise TradeBoardError(f'Page must be 1-{pages}.')
                rows=self.db.execute('SELECT id,trainer,description FROM trade_listings ORDER BY id DESC LIMIT 8 OFFSET ?',((page-1)*8,)).fetchall()
                return [f'Trade board {page}/{pages}:']+([f'{i} {name}: {desc}' for i,name,desc in rows] or ['No active listings.'])
            if op=='contact':
                if len(args)!=1 or not args[0].isascii() or not args[0].isdecimal() or len(args[0])>18 or int(args[0])<1:
                    raise TradeBoardError('Use /trade contact LISTING_ID.')
                row=self.db.execute('SELECT trainer FROM trade_listings WHERE id=?',(int(args[0]),)).fetchone()
                if not row:raise TradeBoardError('Listing not found or expired.')
                if row[0]==trainer:raise TradeBoardError('That is your own listing.')
                return [f'Contact request for {row[0]} (listing {args[0]}).']
            raise TradeBoardError('Invalid command. Use /trade help.')

    def owner(self,listing_id):
        row=self.db.execute('SELECT trainer FROM trade_listings WHERE id=? AND expires>?',(listing_id,self._now())).fetchone()
        return row[0] if row else None
