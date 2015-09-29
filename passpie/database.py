from datetime import datetime
import os
import shutil

from tinydb import TinyDB, Storage, where
import yaml

from .utils import mkdir_open
from .credential import split_fullname, make_fullname


class PasspieStorage(Storage):
    extension = ".pass"

    def __init__(self, path):
        super(PasspieStorage, self).__init__()
        self.path = path

    def delete(self, credentials):
        for cred in credentials:
            dirname, filename = cred["name"], cred["login"] + self.extension
            credpath = os.path.join(self.path, dirname, filename)
            os.remove(credpath)
            if not os.listdir(os.path.dirname(credpath)):
                shutil.rmtree(os.path.dirname(credpath))

    def read(self):
        elements = []
        for rootdir, dirs, files in os.walk(self.path):
            filenames = [f for f in files if f.endswith(self.extension)]
            for filename in filenames:
                docpath = os.path.join(rootdir, filename)
                with open(docpath) as f:
                    elements.append(yaml.load(f.read()))

        return {"_default":
                {idx: elem for idx, elem in enumerate(elements, start=1)}}

    def write(self, data):
        deleted = [c for c in self.read()["_default"].values()
                   if c not in data["_default"].values()]
        self.delete(deleted)

        for eid, cred in data["_default"].items():
            dirname, filename = cred["name"], cred["login"] + self.extension
            credpath = os.path.join(self.path, dirname, filename)
            with mkdir_open(credpath, "w") as f:
                f.write(yaml.dump(dict(cred), default_flow_style=False))


class Database(TinyDB):

    def __init__(self, config, *args, **kwargs):
        self.config = config
        self.path = self.config['path']
        PasspieStorage.extension = self.config['extension']
        kwargs.setdefault('storage', PasspieStorage)
        super(Database, self).__init__(self.path, *args, **kwargs)

    def has_keys(self):
        return os.path.exists(os.path.join(self.path, '.keys'))

    def credential(self, fullname):
        login, name = split_fullname(fullname)
        return self.get((where("login") == login) & (where("name") == name))

    def add(self, fullname, password, comment):
        login, name = split_fullname(fullname)
        credential = dict(fullname=fullname,
                          name=name,
                          login=login,
                          password=password,
                          comment=comment,
                          modified=datetime.now())
        self.insert(credential)
        return credential

    def update(self, values, fullname):
        values['fullname'] = make_fullname(values["login"], values["name"])
        values['modified'] = datetime.now()
        self.table().update(values, (where("fullname") == fullname))

    def credentials(self, fullname=None):
        if fullname:
            try:
                login, name = split_fullname(fullname)
                query = (where("name") == name) & (where("login") == login)
            except ValueError:
                query = where('name') == fullname
                found = self.search(query)
        else:
            found = self.all()

        return sorted(found, key=lambda x: x["name"] + x["login"])

    def remove(self, fullname):
        self.table().remove(where('fullname') == fullname)

    def matches(self, regex):
        credentials = self.search(
            where("name").contains(regex) |
            where("login").contains(regex) |
            where("comment").contains(regex)
        )
        return sorted(credentials, key=lambda x: x["name"] + x["login"])
