
import sqlite3

conn = sqlite3.connect('db.sqlite3')
c = conn.cursor()

# Limpar checkouts antigos que iam dar erro de integridade com a nova FK
c.execute("DELETE FROM checkouts_checkout")
conn.commit()
conn.close()
