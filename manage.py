"""Command-line tasks for the Kurdistan AI Safety Hub app.

  python manage.py init                              create the database
  python manage.py create-superadmin USERNAME        add a superadmin with a one-time password
        [--name "Display name"] [--password PASSWORD]
  python manage.py reset-password USERNAME           give an account a new one-time password
  python manage.py list-admins                       show every account
  python manage.py export                            write a static copy of the site to dist/

Data lives in KAISH_DATA_DIR (default ./instance), the same place the app uses.
"""
import argparse
import getpass
import re
import sys

from werkzeug.security import generate_password_hash

import db as dbm


def connect():
    con = dbm.connect()
    dbm.init(con)
    return con


def cmd_init(_args):
    connect().close()
    print(f"Database ready at {dbm.DB_PATH}")


def cmd_create_superadmin(args):
    username = args.username.strip().lower()
    if not re.fullmatch(r"[a-z0-9._-]{3,32}", username):
        sys.exit("Usernames use 3 to 32 lowercase letters, numbers, dots, dashes or underscores.")
    con = connect()
    if con.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        sys.exit(f"The username {username} already exists. Use reset-password instead.")
    password = args.password
    if password == "-":
        password = getpass.getpass("Password: ")
    one_time = not password
    if one_time:
        password = dbm.temp_password()
    elif len(password) < 10:
        sys.exit("Use at least 10 characters.")
    dbm.create_user(con, username, args.name or username.title(), generate_password_hash(password),
                    "superadmin", must_change=one_time)
    dbm.log(con, None, "Added an admin", f"{username} (superadmin, from the command line)")
    con.commit()
    print(f"Superadmin created: {username}")
    if one_time:
        print(f"One-time password:  {password}")
        print("They'll choose their own password the first time they sign in.")


def cmd_reset_password(args):
    con = connect()
    row = con.execute("SELECT * FROM users WHERE username = ?", (args.username.strip().lower(),)).fetchone()
    if not row:
        sys.exit(f"No account called {args.username}.")
    password = dbm.temp_password()
    con.execute("UPDATE users SET password_hash = ?, must_change_password = 1, session_token = ?, active = 1 WHERE id = ?",
                (generate_password_hash(password), dbm.new_token(), row["id"]))
    con.execute("DELETE FROM login_attempts WHERE key LIKE ?", (row["username"] + "|%",))
    dbm.log(con, None, "Reset a password", f"{row['username']} (from the command line)")
    con.commit()
    print(f"New one-time password for {row['username']}: {password}")


def cmd_list_admins(_args):
    con = connect()
    rows = con.execute("SELECT * FROM users ORDER BY role DESC, username").fetchall()
    if not rows:
        print("No accounts yet. Run: python manage.py create-superadmin USERNAME")
    for r in rows:
        state = "active" if r["active"] else "deactivated"
        pending = ", has not chosen a password yet" if r["must_change_password"] else ""
        print(f"{r['username']:<20} {r['role']:<11} {state}{pending}  (last sign-in: {r['last_login'] or 'never'})")


def cmd_export(_args):
    import build
    build.main()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(fn=cmd_init)
    p = sub.add_parser("create-superadmin")
    p.add_argument("username")
    p.add_argument("--name", default="")
    p.add_argument("--password", default="", help="leave out for a one-time password; '-' to type one")
    p.set_defaults(fn=cmd_create_superadmin)
    p = sub.add_parser("reset-password")
    p.add_argument("username")
    p.set_defaults(fn=cmd_reset_password)
    sub.add_parser("list-admins").set_defaults(fn=cmd_list_admins)
    sub.add_parser("export").set_defaults(fn=cmd_export)
    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
