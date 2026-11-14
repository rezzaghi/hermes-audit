"""Synthetic SQLite fixture for browser tests; contains no real Hermes conversations."""
import json
import sqlite3
import sys
from pathlib import Path

path = Path(sys.argv[1]); path.parent.mkdir(parents=True, exist_ok=True)
conn = sqlite3.connect(path)
conn.executescript('''CREATE TABLE sessions (id TEXT, title TEXT, source TEXT, parent_session_id TEXT);
CREATE TABLE messages (id INTEGER, session_id TEXT, role TEXT, content TEXT,
 tool_call_id TEXT, tool_calls TEXT, tool_name TEXT, timestamp REAL);''')
conn.executemany('INSERT INTO sessions VALUES (?,?,?,?)',
                 [('s','Acme Notes comparison (fictional)','telegram',None),
                  ('t','Sample workspace setup (fictional)','cli',None)])
rows=[]
def message(i,s,role,content,call_id=None,calls=None,tool=None,ts=None):
    rows.append((i,s,role,content,call_id,json.dumps(calls) if calls else None,tool,ts or 1700000000+i))
def call(i,s,tool,args,result):
    cid=f'call{i}'
    message(i,s,'assistant','',calls=[{'id':cid,'function':{'name':tool,'arguments':json.dumps(args)}}])
    message(i+1,s,'tool',result,call_id=cid,tool=tool)
message(1,'s','user','Compare Acme Notes plans (fictional example)')
call(2,'s','web_search',{'query':'Acme official plan comparison'},'{"success":true,"data":"fictional plan table"}')
call(4,'s','terminal',{'command':'rm -rf /tmp/important'},'{"success":false,"exit_code":1}')
call(6,'s','write_file',{'path':'/tmp/docs.md','content':'review me'},'{"success":true}')
message(8,'s','assistant','Here are the sources: </script><script>window.HACKED=true</script>')
call(9,'t','browser_exec',{'code':'click_at_xy(200,300)'},'{"success":true}')
conn.executemany('INSERT INTO messages VALUES (?,?,?,?,?,?,?,?)',rows)
conn.commit();conn.close()
