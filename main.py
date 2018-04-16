import requests
import json
import curses

from enum import Enum, IntEnum

urls = []
responses = []


"""
"In the blackest night, no hidden path shall escape my sight!\\"\\n\\nLink: http://tbe.taleo.net/NA1/ats/careers/requisition.jsp?org=EKKON&cws=38&rid=352","y":49,"x":49}}'
"""

CELL_SYMBOLS = " ╨╞╚╥║╔╠╡╝═╩╗╣╦╬"


class Turn(Enum):
    RIGHT = 1
    LEFT = 3

    def other(self):
        return Turn.LEFT if self == Turn.RIGHT else Turn.RIGHT


class Direction(IntEnum):
    NORTH = 0
    EAST = 1
    SOUTH = 2
    WEST = 3

    def left(self):
        return Direction((self.value + Turn.LEFT.value) % 4)

    def right(self):
        return Direction((self.value + Turn.RIGHT.value) % 4)

    def turn(self, way):
        return Direction((self.value + way.value) % 4)

    def is_closed(self, cell):
        return cell[self.name.lower()] == "BLOCKED"

    def is_open(self, cell):
        return not self.is_closed(cell)

    def symbol(self):
        return "^>v<"[self.value]

    def next_dir(self, cell, way=Turn.LEFT):
        # turn left to start with
        new_dir = self.turn(way)
        # if there is a wall there, follow it around
        while new_dir.is_closed(cell):
            new_dir = new_dir.turn(way.other())
        return new_dir

    def step(self, x, y):
        return x + [0, 1, 0, -1][self.value], y + [-1, 0, 1, 0][self.value]


class Maze(object):
    base_url = "http://www.epdeveloperchallenge.com/api"
    init_url = base_url + "/init"
    move_url = base_url + "/move?mazeGuid={}&direction={}"
    jump_url = base_url + "/jump?mazeGuid={}&x={}&y={}"

    def __init__(self, dir=Direction.EAST):
        self.maze_window = None
        self.debug_window = None
        self.draw_screen()
        self.urls = []
        self.responses = []
        cell = self.post_url(Maze.init_url)
        self.guid = cell["mazeGuid"]
        self.pos = (cell["x"], cell["y"])
        self.last_pos = self.pos
        self.grid = {self.pos: cell}
        self.dir = dir

    def draw_screen(self):
        self.maze_window = create_window_with_border_and_title("MAZE", 50, 50, 0, 0)
        self.debug_window = create_window_with_border_and_title("DEBUG", 50, 130, 0, 55)
        self.debug_window.scrollok(True)

        # draw initial screen

        # fill in unknown area of maze with @ symbols
        # for y in range(0, 100):
        #     self.window.insstr(y, 0, "@" * 100)

        self.maze_window.refresh()

    def draw_cell(self, cell):
        # determine cell representation
        i = 0
        for d in Direction:
            if d.is_open(cell):
                i |= 1 << d
        ch = CELL_SYMBOLS[i]
        # place symbol
        y = cell["y"]
        x = cell["x"]
        self.maze_window.addstr(y, x, ch)
        self.maze_window.move(y, x)
        self.maze_window.refresh()

    def debug(self, text, line: int=None):
        if line is None:
            self.debug_window.addstr(str(text) + "\n")
        else:
            self.debug_window.addstr(line, 0, str(text) + "\n")
            self.debug_window.clrtobot()
        self.debug_window.refresh()

    def post_url(self, url):
        self.urls.append(url)
        i = len(self.urls) - 1
        # print the URL
        self.debug(url + "\n")
        response = requests.post(url)
        self.debug(response.content)
        self.responses.append(response)
        if not response.ok:
            self.debug("*" * 80)
            self.debug("ERROR: status code {}".format(response.status_code))
            self.debug("*" * 80)
            self.debug("Prepare to step through an action replay")
            self.debug_window.getch()
            self.debug("REPLAY", 0)
            for i, (url, response) in enumerate(zip(self.urls, self.responses)):
                self.debug("{}: {}\n{}".format(i, url, response.content))
                self.debug_window.getch()
            response.raise_for_status()
        # Loading the response data into a dict variable
        # json.loads takes in only binary or string variables so using content to fetch binary content
        j_data = json.loads(response.content)
        cell = j_data["currentCell"]
        self.draw_cell(cell)
        return cell

    def move(self, next_dir: Direction = None):
        cell = self.current_cell()
        if next_dir is None:
            next_dir = self.dir.next_dir(cell)
        self.debug("previous direction was {} and new direction is {}".format(self.dir, next_dir))
        next_pos = next_dir.step(*self.pos)
        assert (0, 0) <= next_pos < (100, 100)
        if next_pos in self.grid:
            self.maze_window.move(next_pos[1], next_pos[0])
            self.maze_window.refresh()
        else:
            # need to fetch a new cell
            if self.pos != self.last_pos:
                # but FIRST we need to ask the server to jump to the current position
                self.post_url(Maze.jump_url.format(self.guid, *self.pos))
            # now fetch the new cell
            cell = self.post_url(Maze.move_url.format(self.guid, next_dir.name))
            self.pos = (cell["x"], cell["y"])
            self.last_pos = self.pos
            self.grid[self.pos] = cell
        self.pos = next_pos
        self.dir = next_dir

    def current_cell(self):
        return self.grid[self.pos]

    def completed(self):
        return self.current_cell()["atEnd"]


def create_window_with_border_and_title(title, rows, cols, y, x):
    # create a slightly larger window than needed
    bw = curses.newwin(rows + 2, cols + 2, y, x)
    # draw a border around the main window
    bw.border()
    # add a title
    bw.addstr(0, 5, "[{}]".format(title))
    # force a repaint
    bw.refresh()
    # draw the right size window inside it
    return curses.newwin(rows, cols, y + 1, x + 1)


maze: Maze = None


def main(stdscr):
    try:
        maze = Maze()
        while not maze.completed():
            maze.move()
    finally:
        stdscr.getch()


curses.wrapper(main)
print(maze.grid[maze.last_pos])
