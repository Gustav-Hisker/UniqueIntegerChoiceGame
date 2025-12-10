import json
import os
import random
import string
import subprocess
import sys
import threading
from hashlib import sha256
from os import makedirs
from random import shuffle
from subprocess import Popen, PIPE
from typing import Annotated

import uvicorn
from fastapi import FastAPI, Form, UploadFile, File
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from starlette.responses import StreamingResponse, JSONResponse

pyPath = "./python-submissions/"
cppPath = "./cpp-submissions/"
exePath = "./executable-submissions/"

teamsJsonPath = "./teams.json"

adminPW = "".join([random.choice(string.ascii_letters + string.digits) for _ in range(8)])

compileTimeout = 10
testCode = "./examples/random-integers.py"

USE_DOCKER = True
DEBUG = True

makedirs(pyPath, exist_ok=True)
makedirs(cppPath, exist_ok=True)
makedirs(exePath, exist_ok=True)

if not os.path.exists(teamsJsonPath):
    with open(teamsJsonPath, "w") as f:
        f.write("{}")

with open(teamsJsonPath, "r") as f:
    teams = json.load(f)

scores = {}
muCount = 0
playedGames = 0

class ProgramHandler:
    def __init__(self, path: str, n: int, k: int, w: int, j: int) -> None:
        self.path = path
        self.n = n
        self.k = k
        self.w = w
        self.j = j

        cmd = [
            "docker", "run", "--rm", "-i", "--init",
            "--network", "none",
            "-v", f"{os.path.abspath(path)}:/app/program:ro",
            ("python:3.13-slim" if path.endswith(".py") else "ubuntu:latest"),
            ("python" if path.endswith(".py") else "/app/program")
        ]

        if path.endswith(".py"):
            cmd.append("/app/program")

        cmd.append(f"#{os.path.basename(path)}")

        if not USE_DOCKER:
            if path.endswith(".py"):
                cmd = [sys.executable, path]
            else:
                cmd = [path]

        self.p = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE, text=True, bufsize=1)

        # Send initial input
        self.p.stdin.write(f"{n} {k} {w} {j}\n")
        self.p.stdin.flush()

    def sendSubmissions(self, g: list[int]) -> None:
        self.p.stdin.write(" ".join(map(str, g)) + "\n")
        self.p.stdin.flush()

    def getOutput(self) -> int:
        result = self.p.stdout.readline()
        if result == "":
            # Check if the process died
            retcode = self.p.poll()
            if retcode is not None:
                err = self.p.stderr.read()
                raise Exception(f"Subprocess {self.path} exited with code {retcode}.\nStderr:\n{err}")
            else:
                raise Exception(f"No output received from subprocess {self.path}")
        resInt = -1
        try:
            resInt = int(result.strip())
        except:
            pass
        if 1 <= resInt <= self.k:
            return resInt
        else:
            raise Exception(f"{result.strip()} is no valid output")

    def __del__(self):
        try:
            self.p.terminate()
            # self.p.kill()
        except Exception:
            pass


def game(paths: list[str], k: int, w: int):
    n = len(paths)
    programs = []
    for i, p in enumerate(paths):
        try:
            programs.append(ProgramHandler(p, n, k, w, i))
        except Exception as e:
            while programs:
                del programs[0]
            yield True, -1, i, "Initialisation error: " + str(e)
            return

    scores = [0 for _ in programs]
    submissions = [0 for _ in programs]

    for _ in range(1000):
        for i, p in enumerate(programs):
            try:
                submissions[i] = p.getOutput()
            except Exception as e:
                while programs:
                    del programs[0]
                yield True, -1, i, "Error reading output of the program: " + str(e)
                return

        for i, p in enumerate(programs):
            try:
                p.sendSubmissions(submissions)
            except Exception as e:
                while programs:
                    del programs[0]
                yield True, -1, i, "Error passing the input to program: " + str(e)
                return

        submissionCounts = {}

        for submission in submissions:
            if submission not in submissionCounts:
                submissionCounts[submission] = 1
            else:
                submissionCounts[submission] += 1

        for i, s in enumerate(submissions):
            if submissionCounts[s] <= 1:
                scores[i] += s
                if scores[i] % w == 0:
                    yield False, scores, submissions, "current game state"
                    while programs:
                        del programs[0]
                    yield True, 1, i, "Win"
                    return

        yield False, scores, submissions, "current game state"

    while programs:
        del programs[0]

    yield True, 0, -1, "Draw"
    return


def testProgram(path: str):
    for i in range(25):
        try:
            n = random.randint(2, 100)
            k = random.randint(1, 100)
            w = random.randint(1, 100)
            j = random.randrange(0, n)

            paths = [(path if i == j else testCode) for i in range(n)]

            outcome, program, value = None, None, None
            for cs in game(paths, k, w):
                _, outcome, program, value = cs

            if outcome == -1:
                yield False, value
            else:
                yield True, (i + 1) * 4

        except Exception as e:
            yield False, str(e) + " (either that's my fault or you messed up very badly)"
            return


def allPrograms():
    pys = [pyPath + f for f in os.listdir(pyPath) if os.path.isfile(os.path.join(pyPath, f)) and f.endswith(".py") and not f.endswith(".temp.py")]
    exes = [exePath + f for f in os.listdir(exePath) if os.path.isfile(os.path.join(exePath, f)) and not f.endswith(".temp")]
    return pys + exes


app = FastAPI()


@app.get("/", response_class=HTMLResponse)
async def root():
    with open("html/index.html") as f:
        return f.read()

# PYTHON


@app.post("/upload.py", response_class=HTMLResponse)
async def wrapperUploadPy(team: Annotated[str, Form()], file: UploadFile = File(...)):
    return StreamingResponse(uploadPy(team, file), media_type="html")


def uploadPy(team: Annotated[str, Form()], file: UploadFile = File(...)):
    with open("html/preset.html") as f:
        yield f.read()

    if team is None or team == "" or team.endswith(".temp") or team.endswith(".py"):
        yield "<h1>Fuck Off</h1> This team name is not valid."
        return

    yield "<h2>Submitting python file</h2>"
    yield "<h4>Uploading ...</h4>"
    try:
        with open(pyPath + team + ".temp.py", "wb") as f:
            f.write(file.file.read())
    except Exception as e:
        yield f"There was an error uploading the file:\n {e}"
        yield "<br><a href='/'><button>Return to start page</button></a></body></html>"
        return
    finally:
        file.file.close()

    yield "<p>Upload successful</p>"

    for t in testUpload(pyPath + team + ".temp.py"):
        value, ok = t
        yield value
        if not ok:
            return

    yield "<h3>Saving file</h3>"
    os.replace(pyPath + team + ".temp.py", pyPath + team + ".py")
    yield "<p>Saving successful<p>"

    yield "<h3>Done!<h3>"
    yield "<p>You can now return to start page.</p>"
    yield "<a href='/'><button>Return</button></a>"

    yield "</body></html>"
    return

# C++


@app.post("/upload.cpp", response_class=HTMLResponse)
async def wrapperUploadCpp(team: Annotated[str, Form()], file: UploadFile = File(...)):
    return StreamingResponse(uploadCpp(team, file), media_type="html")


def uploadCpp(team: Annotated[str, Form()], file: UploadFile = File(...)):
    with open("html/preset.html") as f:
        yield f.read()

    if team is None or team == "" or team.endswith(".temp") or team.endswith(".py"):
        yield "<h1>Fuck Off</h1> This team name is not valid."
        return

    yield "<h2>Submitting C++ file</h2>"
    yield "<h4>Uploading ...</h4>"
    try:
        with open(cppPath + team + ".cpp", "wb") as f:
            f.write(file.file.read())
    except Exception as e:
        yield f"<p>There was an error uploading the file:</p><br><code>{e}</code>"
        yield "<br><a href='/'><button>Return to start page</button></a></body></html>"
        return
    finally:
        file.file.close()

    yield "<p>Upload successful</p>"
    yield "<h4>Compiling</h4>"
    yield "<p>Compilation successful</p>"
    es = ""
    try:
        subp = subprocess.run(f"g++ -std=c++20 -o \"{exePath}{team}.temp\" \"{cppPath}{team}.cpp\"", shell=True, capture_output=True, timeout=compileTimeout)
        es = subp.stderr.decode()
        subp.check_returncode()
    except Exception as e:
        yield f"<p>There was an error compiling the your code:</p><code style='color: red'>{e}</code><br><br><p>stderr:</p><code style='color: red'>{es}</code>"
        yield "<br><a href='/'><button>Return to start page</button></a></body></html>"
        return

    for t in testUpload(exePath + team + ".temp"):
        value, ok = t
        yield value
        if not ok:
            return

    yield "<h3>Saving file</h3>"
    os.replace(exePath + team + ".temp", exePath + team)
    yield "<p>Saving successful<p>"

    yield "<h3>Done!<h3>"
    yield "<p>You can now return to start page.</p>"
    yield "<a href='/'><button>Return</button></a>"

    yield "</body></html>"
    return

# EXECUTABLE


@app.post("/upload.exe", response_class=HTMLResponse)
async def wrapperUploadExe(team: Annotated[str, Form()], file: UploadFile = File(...)):
    return StreamingResponse(uploadExe(team, file), media_type="html")


def uploadExe(team: Annotated[str, Form()], file: UploadFile = File(...)):
    with open("html/preset.html") as f:
        yield f.read()

    if team is None or team == "" or team.endswith(".temp") or team.endswith(".py"):
        yield "<h1>Fuck Off</h1> This team name is not valid."
        return

    yield "<h2>Submitting executable</h2>"
    yield "<h4>Uploading ...</h4>"
    try:
        with open(exePath + team + ".temp", "wb") as f:
            f.write(file.file.read())
        subprocess.run(f"chmod +x {exePath}{team}.temp", shell=True, capture_output=True, timeout=compileTimeout, check=True)
    except Exception as e:
        yield f"<p>There was an error uploading the file:</p><br><code>{e}</code>"
        yield "<br><a href='/'><button>Return to start page</button></a></body></html>"
        return
    finally:
        file.file.close()

    yield "<p>Upload successful</p>"

    for t in testUpload(exePath + team + ".temp"):
        value, ok = t
        yield value
        if not ok:
            return

    yield "<h3>Saving file</h3>"
    os.replace(exePath + team + ".temp", exePath + team)
    yield "<p>Saving successful<p>"

    yield "<h3>Done!<h3>"
    yield "<p>You can now return to start page.</p>"
    yield "<a href='/'><button>Return</button></a>"

    yield "</body></html>"
    return


def testUpload(path):
    yield "<h4>Testing upload</h4>", True
    yield '<progress id="pb" max="100" value="0"></progress>', True
    yield "<script>pb = document.getElementById('pb')</script>", True

    for tr in testProgram(path):
        testSuccess, value = tr
        if testSuccess:
            yield f"<script>pb.value={value}</script>", True
        else:
            yield f"<p style='color:red'><b>Error<b> your programm didn't pass the tests. But created this Error:<br><code>{value}</code></p><p>Note that these tests shouldn't be a challenge but just find potential flaws in your code. Your code is tested in $100$ random games with $100$ rounds (every input your program gets, is an input that actually could occur in the game).</p>", True
            yield "<br><a href='/'><button>Return to start page</button></a></body></html>", False
            return

    yield "<p>All tests successful.<p>", True
    return


@app.get("/randomGameDisplay", response_class=HTMLResponse)
async def randomGameDisplay():
    with open("html/random-game.html") as f:
        return f.read()


@app.get("/background.jpeg")
async def background():
    def iterfile():
        with open("assets/background.jpeg", mode="rb") as file_like:
            yield from file_like

    return StreamingResponse(iterfile(), media_type="jpeg")


def getAllMatchUps(programs):
    for n in range(3, 6):
        yield from getAllMatchUpsWithFixedSize(programs, n)


def getAllMatchUpsWithFixedSize(programs, n):
    if n > len(programs):
        return
    if n == 0:
        yield []
        return
    for program in programs:
        for matchUp in getAllMatchUpsWithFixedSize(set(programs) - {program}, n - 1):
            yield matchUp + [program]


@app.get("/randomGame", response_class=JSONResponse)
def randomGame(n: int = 8, k: int = 5, w: int = 20):
    programs = []
    for i in range(n):
        programs.append(random.choice(allPrograms()))

    names = [os.path.basename(f).removesuffix(".py") for f in programs]

    scoreList = []
    submissionList = []
    for gs in game(programs, k, w):
        if gs[0]:
            _, ending, winner, value = gs
            return {"n": n, "k": k, "w": w, "names": names, "score-list": scoreList, "submission-list": submissionList, "ending": ending, "winner": winner, "value": value}
        else:
            scoreList.append(gs[1].copy())
            submissionList.append(gs[2].copy())
    return {"n": n, "k": k, "w": w, "names": names, "score-list": scoreList, "submission-list": submissionList, "ending": -1, "winner": -1, "value": "unknown error"}


class TournamentThread(threading.Thread):
    def __init__(self, mu):
        threading.Thread.__init__(self)
        self.mu = mu

    def run(self):
        global scores, playedGames
        d = 0
        id = 0

        for cs in game(self.mu, 5, 20):
            _, id, d, _ = cs

        scores[self.mu[id]] += d

        playedGames += 1


class pwWrapper(BaseModel):
    pw: str


@app.post("/start-tournament", response_class=JSONResponse)
async def startTournament(wrapper: pwWrapper):
    if wrapper.pw != adminPW:
        return {"ok": False, "error": "Invalid password"}
    global scores, playedGames, muCount
    if muCount > playedGames:
        return {"ok": False, "error": "Tournament is still running"}
    programs = allPrograms()
    scores = {p: 0 for p in programs}
    if len(programs) <= 1:
        return {"ok": False, "error": "Too few players"}
    mus = list(getAllMatchUps(programs))
    shuffle(mus)
    muCount = len(mus)
    playedGames = 0
    starterThread = threading.Thread()
    starterThread.run = lambda: [TournamentThread(mu).start() for mu in mus]
    starterThread.start()
    return {"ok": True}


@app.get("/tournament", response_class=JSONResponse)
async def tournament():
    return {
        "scores": {os.path.basename(f).removesuffix(".py"): s for f, s in scores.items()},
        "played": playedGames,
        "games": muCount,
    }


@app.get("/tournamentDisplay", response_class=HTMLResponse)
async def tournamentDisplay():
    with open("html/tournament.html") as f:
        return f.read()


@app.get("/favicon.ico")
async def favicon():
    def iterfile():
        with open("assets/favicon.ico", mode="rb") as file_like:
            yield from file_like

    return StreamingResponse(iterfile(), media_type="ico")


@app.post("/validatePW", response_class=JSONResponse)
async def validatePW(wrapper: pwWrapper):
    return wrapper.pw == adminPW


@app.get("/admin", response_class=HTMLResponse)
async def admin():
    with open("html/admin.html") as f:
        return f.read()


def pwHash(pw):
    return sha256(pw.encode()).hexdigest()

def saveTeams():
    with open(teamsJsonPath, "w") as f:
        json.dump(teams, f)

class pwTeamWrapper(BaseModel):
    pw: str
    teamName: str

@app.post("/createTeam", response_class=JSONResponse)
async def startTournament(wrapper: pwTeamWrapper):
    if wrapper.pw != adminPW:
        return {"ok": False, "error": "Invalid password"}
    global teams
    if wrapper.teamName in teams:
        return {"ok": False, "error": "Team already exists"}
    teamPW = "".join([random.choice(string.ascii_letters + string.digits) for _ in range(8)])
    h = pwHash(teamPW)
    teams[wrapper.teamName] = h
    saveTeams()
    return {"ok": True, "pw": teamPW}


@app.post("/removeTeam", response_class=JSONResponse)
async def startTournament(wrapper: pwTeamWrapper):
    if wrapper.pw != adminPW:
        return {"ok": False, "error": "Invalid password"}
    global teams
    if wrapper.teamName not in teams:
        return {"ok": False, "error": "Team doesn't exist"}
    del teams[wrapper.teamName]
    saveTeams()
    return {"ok": True}

@app.get("/teams", response_class=JSONResponse)
async def getTeams():
    return list(teams.keys())


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8080)
else:
    print(f"The admin password is: {adminPW}")
