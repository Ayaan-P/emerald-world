"""Trade board UI using existing authenticated in-game chat.

This only advertises and notifies. It does not trigger or consent to a trade.
"""
from .trade_board import TradeBoardError

class TradeChat:
    def __init__(self,server):self.server=server

    def message(self,recipient,sender,text):
        s=self.server
        if not 1<=len(text)<=120 or not text.isascii():raise ValueError('invalid trade board response')
        s.chat_serial+=1
        msg=(s.chat_serial,sender,recipient['id'],text.encode('ascii').hex())
        recipient['chat_history']=(recipient['chat_history']+[msg])[-16:]

    def handle(self,conn,text):
        if text!='/trade' and not text.startswith('/trade '):return False
        s=self.server
        with s.lock:
            try:
                command=text[6:].strip();parts=command.split()
                lines=s.trade_board.command(conn['id'],command)
                if len(parts)==2 and parts[0].lower()=='contact':
                    owner=s.trade_board.owner(int(parts[1]));recipient=s.peers.get(owner)
                    if not recipient or not recipient.get('chat') or recipient.get('closing'):
                        lines=['Trader is offline or has chat unavailable. Try later.']
                    else:
                        self.message(recipient,conn['id'],f'Trade: {conn["id"]} is interested in listing {parts[1]}. Use normal trade.')
                        s._queue(recipient,s._snapshot(recipient))
                        lines=(['Trader became unavailable. Try later.'] if recipient.get('closing') else
                               [f'Request queued for {owner}. Arrange an ordinary consented trade.'])
            except TradeBoardError as exc:lines=[str(exc)]
            for line in lines:self.message(conn,conn['id'],'Trade: '+line)
        conn['chat_status']='sent';s._queue(conn,s._snapshot(conn));return True
