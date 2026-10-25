from pathlib import Path
import argparse,shutil,subprocess,json,urllib.request,time
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--neo4j-home',type=Path,required=True);p.add_argument('--postgres-bin',type=Path,default=Path('/usr/lib/postgresql/16/bin'));args=p.parse_args()
r=args.root.resolve();r.mkdir(parents=True,exist_ok=True)
pg=r/'pgdata';bin=args.postgres_bin
if not pg.exists():
 subprocess.run([str(bin/'initdb'),'-D',str(pg),'-A','trust','--no-locale','--encoding=UTF8'],check=True,stdout=subprocess.DEVNULL)
 with (pg/'postgresql.conf').open('a') as f:f.write("\nlisten_addresses='127.0.0.1'\nport=15432\nunix_socket_directories='"+str(r)+"'\nshared_buffers='1GB'\nwork_mem='64MB'\nmax_connections=20\n")
if not (pg/'postmaster.pid').exists():subprocess.run([str(bin/'pg_ctl'),'-D',str(pg),'-l',str(r/'postgres.log'),'-w','start'],check=True)
base=args.neo4j_home.resolve();neo=r/'neo4j'
if not neo.exists():
 neo.mkdir()
 for d in ('bin','licenses'):shutil.copytree(base/d,neo/d)
 (neo/'lib').symlink_to(base/'lib',target_is_directory=True)
 for d in ('conf','data','logs','run','plugins','import','certificates'):(neo/d).mkdir()
 (neo/'conf/neo4j.conf').write_text('''server.default_listen_address=127.0.0.1
server.http.listen_address=:18774
server.http.advertised_address=:18774
server.bolt.listen_address=:18787
server.bolt.advertised_address=:18787
server.https.enabled=false
dbms.security.auth_enabled=false
server.memory.heap.initial_size=1G
server.memory.heap.max_size=2G
server.memory.pagecache.size=1G
server.jvm.additional=-XX:+UseG1GC
''')
try:urllib.request.urlopen('http://127.0.0.1:18774/',timeout=3)
except Exception:subprocess.run([str(neo/'bin/neo4j'),'start'],check=True)
for _ in range(45):
 try:
  urllib.request.urlopen('http://127.0.0.1:18774/',timeout=2);break
 except Exception:time.sleep(1)
else:raise RuntimeError('Neo4j not ready')
venv=r/'venv'
if not venv.exists():subprocess.run(['python3','-m','venv',str(venv)],check=True)
subprocess.run([str(venv/'bin/pip'),'install','psycopg2-binary==2.9.11'],check=True)
print('Dedicated PostgreSQL 15432 and Neo4j 18774 ready; pre-existing databases untouched.')
