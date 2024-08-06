from __future__ import annotations
from typing import List, Callable, Set, Tuple, Union, TYPE_CHECKING, Dict, Any
import math
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from .structs import SC2MOGenMission

class LayoutType(ABC):
    size: int

    # 0
    # 1
    # 2

    def __init__(self, size: int):
        self.size = size

    def set_options(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """Get type-specific options from the provided dict. Should return unused values."""
        return options

    @abstractmethod
    def make_slots(self, mission_factory: Callable[[], SC2MOGenMission]) -> List[SC2MOGenMission]:
        """Use the provided `Callable` to create a one-dimensional list of mission slots and set up initial settings and connections.

        This should include at least one entrance and exit."""
        return []
    
    def parse_index(self, term: str) -> Union[Set[int], None]:
        """From the given term, determine a list of desired target indices. The term is guaranteed to not be "entrances", "exits", or "all".

        If the term cannot be parsed, either raise a descriptive exception or return `None`."""
        return None

    @abstractmethod
    def get_visual_layout(self) -> List[List[int]]:
        """Organize the mission slots into a list of columns from left to right and top to bottom.
        The list should contain indices into the list created by `make_slots`. Intentionally empty spots should contain -1.
        
        The resulting 2D list should be rectangular."""
        pass

class Column(LayoutType):
    """Linear layout. Default entrance is index 0 at the top, default exit is index `size - 1` at the bottom."""

    def make_slots(self, mission_factory: Callable[[], SC2MOGenMission]) -> List[SC2MOGenMission]:
        missions = [mission_factory() for _ in range(self.size)]
        missions[0].option_entrance = True
        missions[-1].option_exit = True
        for i in range(self.size - 1):
            missions[i].next.add(missions[i + 1])
        return missions
    
    def get_visual_layout(self) -> List[List[int]]:
        return [list(range(self.size))]

class Grid(LayoutType):
    """Rectangular grid. Default entrance is index 0 in the top left, default exit is index `size - 1` in the bottom right."""
    width: int
    height: int
    num_corners_to_remove: int
    two_start_positions: bool

    # 0 1 2
    # 3 4 5
    # 6 7 8

    def set_options(self, options: Dict[str, Any]) -> Dict[str, Any]:
        self.two_start_positions = options.pop("two_start_positions", False)
        if self.two_start_positions:
            self.size += 1
        width: int = options.pop("width", 0)
        if width < 1:
            self.width, self.height, self.num_corners_to_remove = Grid.get_grid_dimensions(self.size)
        else:
            self.width = width
            self.height = math.ceil(self.size / self.width)
            self.num_corners_to_remove = self.height * width - self.size
        return options

    @staticmethod
    def get_factors(number: int) -> Tuple[int, int]:
        """
        Simple factorization into pairs of numbers (x, y) using a sieve method.
        Returns the factorization that is most square, i.e. where x + y is minimized.
        Factor order is such that x <= y.
        """
        assert number > 0
        for divisor in range(math.floor(math.sqrt(number)), 1, -1):
            quotient = number // divisor
            if quotient * divisor == number:
                return divisor, quotient
        return 1, number

    @staticmethod
    def get_grid_dimensions(size: int) -> Tuple[int, int, int]:
        """
        Get the dimensions of a grid mission order from the number of missions, int the format (x, y, error).
        * Error will always be 0, 1, or 2, so the missions can be removed from the corners that aren't the start or end.
        * Dimensions are chosen such that x <= y, as buttons in the UI are wider than they are tall.
        * Dimensions are chosen to be maximally square. That is, x + y + error is minimized.
        * If multiple options of the same rating are possible, the one with the larger error is chosen,
        as it will appear more square. Compare 3x11 to 5x7-2 for an example of this.
        """
        dimension_candidates: List[Tuple[int, int, int]] = [(*Grid.get_factors(size + x), x) for x in (2, 1, 0)]
        best_dimension = min(dimension_candidates, key=sum)
        return best_dimension

    def get_grid_coordinates(self, idx: int) -> Tuple[int, int]:
        return math.floor(idx / self.width), (idx % self.width)
    
    def get_grid_index(self, x: int, y: int) -> int:
        return y * self.width + x
    
    def is_valid_coordinates(self, x: int, y: int) -> bool:
        return (
            x >= 0 and x < self.width and
            y >= 0 and y < self.height
        )

    def make_slots(self, mission_factory: Callable[[], SC2MOGenMission]) -> List[SC2MOGenMission]:
        missions = [mission_factory() for _ in range(self.width * self.height)]
        if self.two_start_positions:
            missions[0].option_empty = True
            missions[1].option_entrance = True
            missions[self.get_grid_index(0, 1)].option_entrance = True
        else:
            missions[0].option_entrance = True
        missions[-1].option_exit = True

        for x in range(self.width):
            left = x - 1
            right = x + 1
            for y in range(self.height):
                up = y - 1
                down = y + 1
                idx = self.get_grid_index(x, y)
                neighbours = [
                    self.get_grid_index(nb_x, nb_y)
                    for (nb_x, nb_y) in [(left, y), (right, y), (x, up), (x, down)]
                    if self.is_valid_coordinates(nb_x, nb_y)
                ]
                missions[idx].next = {missions[nb] for nb in neighbours}
        
        # Empty corners
        top_corners = math.floor(self.num_corners_to_remove / 2)
        bottom_corners = math.ceil(self.num_corners_to_remove / 2)

        # Bottom left corners
        y = self.height - 1
        x = 0
        leading_x = 0
        placed = 0
        while placed < bottom_corners:
            if x == -1 or y == 0:
                leading_x += 1
                x = leading_x
                y = self.height - 1
            missions[self.get_grid_index(x, y)].option_empty = True
            placed += 1
            x -= 1
            y -= 1

        # Top right corners
        y = 0
        x = self.width - 1
        leading_x = self.width - 1
        placed = 0
        while placed < top_corners:
            if x == self.width or y == self.height - 1:
                leading_x -= 1
                x = leading_x
                y = 0
            missions[self.get_grid_index(x, y)].option_empty = True
            placed += 1
            x += 1
            y += 1

        return missions
    
    def get_visual_layout(self) -> List[List[int]]:
        columns = [
            [self.get_grid_index(x, y) for y in range(self.height)]
            for x in range(self.width)
        ]
        return columns
    
    def parse_index(self, term: str) -> Union[Set[int], None]:
        raise NotImplementedError
    
class Hopscotch(LayoutType):
    """Alternating between one and two available missions.
    Default entrance is index 0 in the top left, default exit is index `size - 1` in the bottom right."""
    width: int
    two_start_positions: bool

    # 0 2
    # 1 3 5
    #   4 6
    #     7

    def set_options(self, options: Dict[str, Any]) -> Dict[str, Any]:
        self.two_start_positions = options.pop("two_start_positions", False)
        if self.two_start_positions:
            self.size += 1
        width: int = options.pop("width", 7)
        self.width = max(width, 4)
        return options

    def make_slots(self, mission_factory: Callable[[], SC2MOGenMission]) -> List[SC2MOGenMission]:
        slots = [mission_factory() for _ in range(self.size)]
        if self.two_start_positions:
            slots[0].option_empty = True
            slots[1].option_entrance = True
            slots[2].option_entrance = True
        else:
            slots[0].option_entrance = True
        slots[-1].option_exit = True

        cycle = 0
        for idx in range(self.size):
            match cycle:
                case 0:
                    indices = [idx + 1, idx + 2]
                    cycle = 2
                case 1:
                    indices = [idx + 1]
                    cycle -= 1
                case 2:
                    indices = [idx + 2]
                    cycle -= 1
            for next_idx in indices:
                if next_idx < self.size:
                    slots[idx].next.add(slots[next_idx])
        
        return slots
    
    @staticmethod
    def space_at_column(idx: int) -> List[int]:
        # -1 0 1 2 3 4 5
        amount = idx - 1
        if amount > 0:
            return [-1 for _ in range(amount)]
        else:
            return []

    def get_visual_layout(self) -> List[List[int]]:
        spacer = self.width - 3
        # size offset by 1 to account for first column of two slots
        cols: List[List[int]] = []
        col: List[int] = []
        col_size = 1
        for idx in range(self.size):
            if col_size == 3:
                col_size = 1
                cols.append(col)
                col = [idx]
            else:
                col_size += 1
                col.append(idx)
        if len(col) > 0:
            cols.append(col)

        final_cols: List[List[int]] = [Hopscotch.space_at_column(idx) for idx in range(min(len(cols), self.width))]
        for (col_idx, col) in enumerate(cols):
            if col_idx >= self.width:
                final_cols[col_idx % self.width].extend([-1 for _ in range(spacer)])
            final_cols[col_idx % self.width].extend(col)
        
        fill_to_longest(final_cols)

        return final_cols

class Gauntlet(LayoutType):
    """Long, linear layout. Goes horizontally and wraps around.
    Default entrance is index 0 in the top left, default exit is index `size - 1` in the bottom right."""
    width: int

    # 0 1 2 3
    #
    # 4 5 6 7
    
    def set_options(self, options: Dict[str, Any]) -> Dict[str, Any]:
        width: int = options.pop("width", 7)
        self.width = min(max(width, 4), self.size)
        return options

    def make_slots(self, mission_factory: Callable[[], SC2MOGenMission]) -> List[SC2MOGenMission]:
        missions = [mission_factory() for _ in range(self.size)]
        missions[0].option_entrance = True
        missions[-1].option_exit = True
        for i in range(self.size - 1):
            missions[i].next.add(missions[i + 1])
        return missions
    
    def get_visual_layout(self) -> List[List[int]]:
        columns = [[] for _ in range(self.width)]
        for idx in range(self.size):
            if idx >= self.width:
                columns[idx % self.width].append(-1)
            columns[idx % self.width].append(idx)

        fill_to_longest(columns)

        return columns

class Blitz(LayoutType):
    """Rows of missions, one mission per row required.
    Default entrances are every mission in the top row, default exit is a central mission in the bottom row."""
    width: int

    # 0 1 2 3
    # 4 5 6 7

    def set_options(self, options: Dict[str, Any]) -> Dict[str, Any]:
        width = options.pop("width", 0)
        if width < 1:
            min_width, max_width = 2, 5
            mission_divisor = 5
            self.width = min(max(self.size // mission_divisor, min_width), max_width)
        else:
            self.width = min(self.size, width)
        return options
    
    def make_slots(self, mission_factory: Callable[[], SC2MOGenMission]) -> List[SC2MOGenMission]:
        slots = [mission_factory() for _ in range(self.size)]
        for idx in range(self.width):
            slots[idx].option_entrance = True
        
        # TODO: this is copied from the original mission order and works, but I'm not sure on the intent
        # middle_column = self.width // 2
        # if self.size % self.width > middle_column:
        #     final_row = self.width * (self.size // self.width)
        #     final_mission = final_row + middle_column
        # else:
        #     final_mission = self.size - 1
        # slots[final_mission].option_exit = True
        slots[-1].option_exit = True

        rows = self.size // self.width
        for row in range(rows):
            for top in range(self.width):
                idx = row * self.width + top
                for bot in range(self.width):
                    other = (row + 1) * self.width + bot
                    if other < self.size:
                        slots[idx].next.add(slots[other])
        
        return slots
    
    def get_visual_layout(self) -> List[List[int]]:
        columns = [[] for _ in range(self.width)]
        for idx in range(self.size):
            columns[idx % self.width].append(idx)
        
        fill_to_longest(columns)

        return columns
    
def fill_to_longest(columns: List[List[int]]):
    longest = max(len(col) for col in columns)
    for idx in range(len(columns)):
        length = len(columns[idx])
        if length < longest:
            columns[idx].extend([-1 for _ in range(longest - length)])