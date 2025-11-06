import json
import os
import random
import subprocess
import sys
from os import makedirs
from subprocess import Popen, PIPE
from typing import Annotated

import uvicorn
from fastapi import FastAPI, Form, UploadFile, File
from fastapi.responses import HTMLResponse
from starlette.responses import StreamingResponse, JSONResponse

pyPath = "./python-submissions/"
cppPath = "./cpp-submissions/"
exePath = "./executable-submissions/"

compileTimeout = 10
testCode = "./examples/random-integers.py"

makedirs(pyPath, exist_ok=True)
makedirs(cppPath, exist_ok=True)
makedirs(exePath, exist_ok=True)

class ProgramHandler:
    def __init__(self, path: str, n: int, k: int, w: int, j: int) -> None:
        self.path = path
        self.n = n
        self.k = k
        self.w = w
        self.j = j

        if path.endswith(".py"):
            self.p = Popen([sys.executable, "-u", path], stdin=PIPE, stdout=PIPE, stderr=PIPE, text=True, bufsize=1)
        else:
            self.p = Popen(path, stdin=PIPE, stdout=PIPE, stderr=PIPE, text=True, bufsize=1)

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
            self.p.kill()
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
            return True,-1, i, "Initialisation error: " + str(e)

    scores = [0 for _ in programs]
    submissions = [0 for _ in programs]

    for _ in range(1000):
        for i, p in enumerate(programs):
            try:
                submissions[i] = p.getOutput()
            except Exception as e:
                while programs:
                    del programs[0]
                yield True,-1, i, "Error reading output of the program: " + str(e)
                return

        for i, p in enumerate(programs):
            try:
                p.sendSubmissions(submissions)
            except Exception as e:
                while programs:
                    del programs[0]
                yield True,-1, i, "Error passing the input to program: " + str(e)
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
                if scores[i]%w == 0:
                    yield False, scores, submissions, "current game state"
                    while programs:
                        del programs[0]
                    yield True,1, i, "Win"
                    return

        yield False, scores, submissions, "current game state"

    while programs:
        del programs[0]


    yield True,0, -1, "Draw"
    return


def testProgram(path: str):
    for i in range(100):
        try:
            n = random.randint(2,100)
            k = random.randint(1,100)
            w = random.randint(1,100)
            j = random.randrange(0,n)

            paths = [(path if i == j else testCode) for i in range(n)]


            outcome, program, value = None, None, None
            for cs in game(paths, k, w):
                _, outcome, program, value = cs

            if outcome == -1:
                yield False, value
            else:
                yield True, i+1

        except Exception as e:
            yield False, str(e) + " (either that's my fault or you messed up very badly)"
            return


def allPrograms():
    pys = [pyPath+f for f in os.listdir(pyPath) if os.path.isfile(os.path.join(pyPath, f)) and f.endswith(".py") and not f.endswith(".temp.py")]
    exes = [exePath+f for f in os.listdir(exePath) if os.path.isfile(os.path.join(exePath, f)) and not f.endswith(".temp")]
    return pys + exes


app = FastAPI()


@app.get("/", response_class=HTMLResponse)
def root():
    with open("index.html") as f:
        return f.read()

# PYTHON
@app.post("/upload.py", response_class=HTMLResponse)
def wrapperUploadPy(team: Annotated[str, Form()], file: UploadFile = File(...)):
    return StreamingResponse(uploadPy(team, file), media_type="html")

def uploadPy(team: Annotated[str, Form()], file: UploadFile = File(...)):
    with open("preset.html") as f:
        yield f.read()

    if team is None or team == "" or team.endswith(".temp") or team.endswith(".py"): yield "<h1>Fuck Off</h1> This team name is not valid."; return

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
        if not ok: return

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
def wrapperUploadCpp(team: Annotated[str, Form()], file: UploadFile = File(...)):
    return StreamingResponse(uploadCpp(team, file), media_type="html")

def uploadCpp(team: Annotated[str, Form()], file: UploadFile = File(...)):
    with open("preset.html") as f:
        yield f.read()

    if team is None or team == "" or team.endswith(".temp") or team.endswith(".py"): yield "<h1>Fuck Off</h1> This team name is not valid."; return

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
        subp = subprocess.run(f"g++ -std=c++20 -o {exePath}{team}.temp {cppPath}{team}.cpp",shell=True, capture_output=True, timeout=compileTimeout)
        es = subp.stderr.decode()
        subp.check_returncode()
    except Exception as e:
        yield f"<p>There was an error compiling the your code:</p><code style='color: red'>{e}</code><br><br><p>stderr:</p><code style='color: red'>{es}</code>"
        yield "<br><a href='/'><button>Return to start page</button></a></body></html>"
        return

    for t in testUpload(exePath + team + ".temp"):
        value, ok = t
        yield value
        if not ok: return

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
def wrapperUploadExe(team: Annotated[str, Form()], file: UploadFile = File(...)):
    return StreamingResponse(uploadExe(team, file), media_type="html")

def uploadExe(team: Annotated[str, Form()], file: UploadFile = File(...)):
    with open("preset.html") as f:
        yield f.read()

    if team is None or team == "" or team.endswith(".temp") or team.endswith(".py"): yield "<h1>Fuck Off</h1> This team name is not valid."; return

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
        if not ok: return

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
def randomGameDisplay():
    with open("random-game.html") as f:
        return f.read()


@app.get("/chalkFont.ttf")
def loadgif():
    def iterfile():
        with open("./chalk-font.ttf", mode="rb") as file_like:
            yield from file_like

    return StreamingResponse(iterfile(), media_type="ttf")


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
            return {"n":n,"k":k,"w":w,"names":names,"score-list":scoreList, "submission-list":submissionList, "ending": ending, "winner": winner, "value": value}
        else:
            scoreList.append(gs[1].copy())
            submissionList.append(gs[2].copy())
    return {"n":n,"k":k,"w":w,"names":names,"score-list":scoreList, "submission-list":submissionList, "ending": -1, "winner": -1, "value": "unknown error"}


def getAllMatchUps(programs,n):
    if n == 0:
        yield []
        return
    for program in programs:
        for matchUp in getAllMatchUps(programs, n-1):
            yield matchUp + [program]

@app.get("/tournament", response_class=JSONResponse)
def tournament(n: int = 5, k: int = 5, w: int = 20):
    programs = allPrograms()
    overallScore = {p:0 for p in programs}
    assert n>=2
    for mu in getAllMatchUps(programs, n):
        outcome, program = None, None
        for cs in game(mu, k, w):
            _, outcome, program, _ = cs

        if outcome == -1:
            overallScore[mu[program]] -= 1
        elif outcome == 1:
            overallScore[mu[program]] += 1

    return overallScore


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000)