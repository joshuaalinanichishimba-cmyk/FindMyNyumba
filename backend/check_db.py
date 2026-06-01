import psycopg2
conn = psycopg2.connect('postgresql://postgres:26097801272826@db.nternkltoqadmwfwynzl.supabase.co:5432/postgres')
cur = conn.cursor()
cur.execute('SELECT id, email, role, is_active, created_at FROM users ORDER BY id;')
rows = cur.fetchall()
print('Total users:', len(rows))
for r in rows:
    print(r)
conn.close()
