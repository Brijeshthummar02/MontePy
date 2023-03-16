import itertools
from mcnpy.data_inputs.cell_modifier import CellModifierInput
from mcnpy.data_inputs.lattice import Lattice
from mcnpy.errors import *
from mcnpy.input_parser.mcnp_input import Jump
from mcnpy.input_parser.syntax_node import ValueNode
from mcnpy.mcnp_object import MCNP_Object


class LatticeInput(CellModifierInput):
    """
    Object to handle the inputs from ``LAT``.

    :param input_card: the Card object representing this data card
    :type input_card: Card
    :param comments: The list of Comments that may proceed this or be entwined with it.
    :type comments: list
    :param in_cell_block: if this card came from the cell block of an input file.
    :type in_cell_block: bool
    :param key: the key from the key-value pair in a cell
    :type key: str
    :param value: the value from the key-value pair in a cell
    :type value: str
    """

    def __init__(
        self, input=None, comments=None, in_cell_block=False, key=None, value=None
    ):
        """
        :param input: the Input object representing this data card
        :type input: Input
        :param comments: The list of Comments that may proceed this or be entwined with it.
        :type comments: list
        :param in_cell_block: if this card came from the cell block of an input file.
        :type in_cell_block: bool
        :param key: the key from the key-value pair in a cell
        :type key: str
        :param value: the value from the key-value pair in a cell
        :type value: str
        """
        super().__init__(input, comments, in_cell_block, key, value)
        self._lattice = None
        if self.in_cell_block:
            if key:
                try:
                    val = value["data"][0]
                    val._convert_to_int()
                    val = Lattice(val.value)
                except (ValueError) as e:
                    raise ValueError("Cell Lattice must be 1 or 2")
                self._lattice = val
        elif input:
            self._lattice = []
            words = self.data
            for word in words:
                if isinstance(word, ValueNode):
                    try:
                        value = word
                        value._convert_to_int()
                        self._lattice.append(Lattice(value.value))
                    except ValueError:
                        raise MalformedInputError(
                            input, f"Cell lattice must be 1 or 2. {word} given."
                        )
                elif isinstance(word, Jump):
                    self._lattice.append(word)
                else:
                    raise TypeError(
                        f"Word: {word} cannot be parsed as a lattice as a str, or Jump"
                    )

    @staticmethod
    def _class_prefix():
        return "lat"

    @staticmethod
    def _has_number():
        return False

    @staticmethod
    def _has_classifier():
        return 0

    @property
    def has_information(self):
        if self.in_cell_block:
            return self.lattice is not None

    @property
    def lattice(self):
        """
        The type of lattice being used.

        :rtype: Lattice
        """
        return self._lattice

    @lattice.setter
    def lattice(self, value):
        if not isinstance(value, (Lattice, int, type(None))):
            raise TypeError(
                "lattice must be set to a Lattice, or an integer, {value} given"
            )
        if isinstance(value, int):
            try:
                value = Lattice(value)
            except ValueError:
                raise ValueError("Value: {value} is not a valid Lattice number")
        self._mutated = True
        self._lattice = value

    @lattice.deleter
    def lattice(self):
        self._mutated = True
        self._lattice = None

    def push_to_cells(self):
        if self._problem and not self.in_cell_block:
            self._starting_num_cells = len(self._problem.cells)
            cells = self._problem.cells
            if self._lattice:
                self._check_redundant_definitions()
                for cell, lattice in itertools.zip_longest(
                    cells, self._lattice, fillvalue=None
                ):
                    if not isinstance(lattice, (Jump, type(None))):
                        cell.lattice = lattice

    def merge(self, other):
        raise MalformedInputError(
            other, "Cannot have two lattice inputs for the problem"
        )

    def _clear_data(self):
        del self._lattice

    def __str__(self):
        return "Lattice: {self.lattice}"

    def __repr__(self):
        ret = (
            f"Lattice: in_cell: {self._in_cell_block}"
            f" set_in_block: {self.set_in_cell_block}, "
            f"Lattice_values : {self._lattice}"
        )
        return ret

    def format_for_mcnp_input(self, mcnp_version):
        ret = []
        if self.in_cell_block:
            if self.lattice:
                ret.extend(
                    self.wrap_string_for_mcnp(
                        f"LAT={self.lattice.value}",
                        mcnp_version,
                        False,
                    )
                )
        else:
            mutated = self.mutated
            if not mutated:
                mutated = self.has_changed_print_style
                if self._starting_num_cells != len(self._problem.cells):
                    mutated = True
                for cell in self._problem.cells:
                    if cell._lattice.mutated:
                        mutated = True
                        break
            if mutated and self._problem.print_in_data_block["LAT"]:
                has_info = False
                for cell in self._problem.cells:
                    if cell._lattice.has_information:
                        has_info = True
                        break
                if has_info:
                    ret = MCNP_Card.format_for_mcnp_input(self, mcnp_version)
                    ret_strs = ["LAT"]
                    lattices = []
                    for cell in self._problem.cells:
                        if cell.lattice:
                            lattices.append(cell.lattice.value)
                        else:
                            lattices.append(Jump())
                    ret_strs.extend(
                        self.compress_jump_values(
                            self.compress_repeat_values(lattices, 1e-1)
                        )
                    )
                    ret.extend(self.wrap_words_for_mcnp(ret_strs, mcnp_version, True))
            elif self._problem.print_in_data_block["LAT"]:
                ret = self._format_for_mcnp_unmutated(mcnp_version)
        return ret
