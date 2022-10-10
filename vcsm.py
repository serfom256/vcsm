import os
import sys
import uuid
import shelve
import pathlib
import hashlib
import shutil
from pathlib import Path


COMMIT_WORK_TREE = ".vcsm"
DB = "vcsmdb"
LAUNCH_PATH = pathlib.Path().resolve()
PATH = LAUNCH_PATH


class Command:
    def __init__(self):
        self.commands = dict()
        self.commands["init"] = self.init_worktree
        self.commands["purge"] = self.purge_worktree
        self.commands["commit"] = self.do_commit
        self.commands["lc"] = self.get_all_commits
        self.commands["rollback"] = self.rollback

    def exec(self, cmd, args=None):
        return self.commands[cmd](args)

    def init_worktree(self, args=None):
        try:
            if not os.path.exists(os.path.join(PATH, COMMIT_WORK_TREE)):
                os.makedirs(COMMIT_WORK_TREE)
            else:
                return "The Vcsm root has already been initialized here"
            return "An empty Vcsm root inited"
        except FileExistsError:
            return "Cannot init an empty Vcsm root"

    def purge_worktree(self, args=None):
        try:
            if not os.path.exists(os.path.join(PATH, COMMIT_WORK_TREE)):
                return "The Vcsm was't initialized here"
            folder = os.path.join(PATH, COMMIT_WORK_TREE)
            for f in os.listdir(folder):
                self.__purge_dir(Path(os.path.join(folder, f)))
            return "Vcsm root purged"
        except FileExistsError:
            return "Cannot purge Vcsm root"

    def rollback(self, args=None):
        if args is None:
            return "Invalid arguments for rollback use -h flag to get info"
        commit_hash = args[0]
        commits = self.__load_commits()
        if commit_hash in commits:
            prev_hashes = commits[commit_hash].hash.indexes
            self.__compare_and_fix(prev_hashes,
                                   Hash(LAUNCH_PATH).indexes,
                                   Path(LAUNCH_PATH)
                                   )

            for k, v in prev_hashes.items():
                print("Discrepancy in object:", k, v)
            return "Rollback to " + commit_hash
        else:
            return "No such hash"

    def __find_work_tree(self, dir):
        files = set([f for f in os.listdir(dir)])
        return COMMIT_WORK_TREE in files

    def __compare_and_fix(self, pi, ci, path, rel_path=""):
        if not path.is_dir():
            return
        for np in path.iterdir():
            name = os.path.join(rel_path, os.path.basename(np.name))
            if name in pi and pi[name] == ci[name]:
                del pi[name]
            elif name != COMMIT_WORK_TREE:
                if name not in pi:
                    print("To remove:", name)
                    self.__purge_dir(np)
                self.__compare_and_fix(pi, ci, np, name)

    def __purge_dir(self, path):
        if path.is_dir():
            shutil.rmtree(path)
        else:
            os.remove(path)

    def get_all_commits(self, args=None):
        if not self.__find_work_tree(PATH):
            return "Vcs not initialized here!"
        commits = self.__load_commits()
        res = ""
        for _, c in commits.items():
            res += str(c) + "\n"
        return res

    def do_commit(self, commit_name):
        if commit_name is None or len(commit_name) == 0:
            return "Commit message must be specified!"
        if not self.__find_work_tree(PATH):
            return "Vcs not initialized here!"
        commit_name = " ".join(commit_name)
        commit = Commit(commit_name, PATH)
        res = self.__save_commit(commit)
        return res + str(commit)

    def __save_commit(self, commit):
        with shelve.open(os.path.join(PATH, COMMIT_WORK_TREE, DB)) as worktree:
            if commit.hash.hash in worktree:
                return "Already commited"
            worktree[str(commit.hash.hash)] = commit
            return "Commited: "

    def __load_commits(self):
        res = dict()
        with shelve.open(os.path.join(PATH, COMMIT_WORK_TREE, DB)) as worktree:
            for k, v in worktree.items():
                res[k] = v
        return res


class Commit:
    def __init__(self, name, path):
        self.uid = uuid.uuid4().hex
        self.hash = Hash(path)
        self.name = name

    def __str__(self):
        return "Commit: "+self.name+"\n\tUUID: "+self.uid+"\n\tHash: "+self.hash.hash


class Hash:
    def __init__(self, path):
        self.path = Path(path)
        self.indexes = dict()
        self.hash = self.__get_hash()

    def __make_hash(self, filename, hash):
        with open(str(filename), "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hash.update(chunk)
        return hash

    def __make_pure_hash(self, file):
        hash = hashlib.md5()
        with open(str(file), "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hash.update(chunk)
        return hash

    def __make_hash_on_dir(self, path, hash, rel_path=""):
        for path in sorted(path.iterdir(), key=lambda p: str(p).lower()):
            hash.update(path.name.encode())
            if path.is_file():
                hash = self.__make_hash(path, hash)
                self.indexes[os.path.join(rel_path, os.path.basename(path))] = str(
                    self.__make_pure_hash(path).hexdigest())
            elif path.name != COMMIT_WORK_TREE:
                hash = self.__make_hash_on_dir(
                    path, hash, os.path.join(rel_path, os.path.basename(path)))
                self.indexes[os.path.join(rel_path, os.path.basename(path))] = str(
                    hash.hexdigest())
        return hash

    def __get_hash(self):
        hash = None
        if self.path.is_dir:
            hash = self.__make_hash_on_dir(self.path, hashlib.md5())
        else:
            hash = self.__make_hash(self.path, hashlib.md5())
        return str(hash.hexdigest())

    def __eq__(self, o):
        return self.hash == o.hash

    def __hash__(self):
        return hash(self.hash)


command = Command()


def main(args):
    if len(args) == 0 or args[0].lower() == "-h":
        print(print_help())
        return
    args = list(map(lambda i: i.lower(), args))
    next = list() if len(args) < 1 else args[1:]
    print(command.exec(args[0], next))


def print_help():
    return """
All available options:
    -h - get help
    init - init vcsm root in the current directory
    commit - commits the current state of the path
    rollback - rollback to commit by the commit hash
    lc(list of commits) - get list of all commits
    """


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        pass
    except Exception:
        print("Invalid commmand, use -h flag to get more information")
