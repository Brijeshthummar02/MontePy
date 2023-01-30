from mcnpy.data_inputs import data_input, thermal_scattering
from mcnpy.data_inputs.isotope import Isotope
from mcnpy.data_inputs.material_component import MaterialComponent
from mcnpy import mcnp_object
from mcnpy.numbered_mcnp_object import Numbered_MCNP_Object
from mcnpy.errors import *
from mcnpy.utilities import *
import itertools
import re


class Material(data_input.DataInputAbstract, Numbered_MCNP_Object):
    """
    A class to represent an MCNP material.

    :param input_card: the input card that contains the data
    :type input_card: Card
    :param comments: The comments card that preceded this card if any.
    :type comments: list
    """

    def __init__(self, input=None, comment=None):
        super().__init__(input, comment)
        self._material_components = {}
        self._thermal_scattering = None
        self._material_number = -1
        if input:
            words = self.words
            # material numbers
            num = self._input_number
            self._old_material_number = num
            self._material_number = num
            words_iter = iter(words[1:])
            set_atom_frac = False
            self._parameter_string = ""
            for isotope_str in words_iter:
                try:
                    isotope = Isotope(isotope_str)
                    fraction = next(words_iter)
                    fraction = fortran_float(fraction)
                except MalformedInputError:
                    self._parameter_string += " ".join(
                        itertools.chain([isotope_str], words_iter)
                    )
                    break
                except ValueError:
                    raise MalformedInputError(
                        input,
                        f"{fraction} could not be parsed as a material fraction",
                    )
                if not set_atom_frac:
                    set_atom_frac = True
                    if fraction > 0:
                        self._is_atom_fraction = True
                    else:
                        self._is_atom_fraction = False
                else:
                    # if switching fraction formatting
                    if (fraction > 0 and not self._is_atom_fraction) or (
                        fraction < 0 and self._is_atom_fraction
                    ):
                        raise MalformedInputError(
                            input,
                            "Material definitons cannot use atom and mass fraction at the same time",
                        )
                self._material_components[isotope] = MaterialComponent(
                    isotope, abs(fraction)
                )

    @property
    def allowed_keywords(self):
        return {
            "GAS",
            "ESTEP",
            "HSTEP",
            "NLIB",
            "PLIB",
            "PNLIB",
            "ELIB",
            "HLIB",
            "ALIB",
            "SLIB",
            "TLIB",
            "DLIB",
            "COND",
            "REFI",
            "REFC",
            "REFS",
        }

    @property
    def old_number(self):
        """
        The material number that was used in the read file

        :rtype: int
        """
        return self._old_material_number

    @property
    def number(self):
        """
        The number to use to identify the material by

        :rtype: int
        """
        return self._material_number

    @number.setter
    def number(self, number):
        if not isinstance(number, int):
            raise TypeError("number must be an int")
        if number <= 0:
            raise ValueError("number must be > 0")
        if self._problem:
            self._problem.materials.check_number(number)
        self._mutated = True
        self._material_number = number

    @property
    def is_atom_fraction(self):
        """
        If true this constituent is in atom fraction, not weight fraction.

        :rtype: bool
        """
        return self._is_atom_fraction

    @property
    def material_components(self):
        """
        The internal dictionary containing all the components of this material.

        :rtype: dict
        """
        # TODO allow detecting mutation of components
        return self._material_components

    @property
    def parameter_string(self):
        """
        String containing the key value pairs specified if any

        :rtype: str
        """
        return self._parameter_string

    @property
    def thermal_scattering(self):
        """
        The thermal scattering law for this material

        :rtype: ThermalScatteringLaw
        """
        return self._thermal_scattering

    @property
    def cells(self):
        """A generator of the cells that use this material.

        :returns: an iterator of the Cell objects which use this.
        :rtype: generator
        """
        if self._problem:
            for cell in self._problem.cells:
                if cell.material == self:
                    yield cell

    def add_thermal_scattering(self, law):
        """
        Adds thermal scattering law to the material

        :param law: the law that is mcnp formatted
        :type law: str
        """
        if not isinstance(law, str):
            raise TypeError("Thermal Scattering law must be a string")
        self._thermal_scattering = thermal_scattering.ThermalScatteringLaw(
            material=self
        )
        self._thermal_scattering.add_scattering_law(law)

    def update_pointers(self, data_inputs):
        """
        Updates pointer to the thermal scattering data

        :param data_inputs: a list of the data inputs in the problem
        :type data_inputs: list
        """
        for input in list(data_inputs):
            if isinstance(input, thermal_scattering.ThermalScatteringLaw):
                if input.old_number == self.number:
                    if not self._thermal_scattering:
                        self._thermal_scattering = input
                        input._parent_material = self
                        data_inputs.remove(input)
                    else:
                        raise MalformedInputError(
                            self, "Multiple MT inputs were specified for this material."
                        )

    @property
    def _class_prefix(self):
        return "m"

    @property
    def _has_number(self):
        return True

    @property
    def _has_classifier(self):
        return 0

    def __repr__(self):
        ret = f"MATERIAL: {self.number} fractions: "
        if self.is_atom_fraction:
            ret += "atom\n"
        else:
            ret += "mass\n"

        for component in self.material_components:
            ret += str(self.material_components[component]) + "\n"
        if self.thermal_scattering:
            ret += f"Thermal Scattering: {self.thermal_scattering}"

        return ret

    def __str__(self):
        elements = self._get_material_elements()
        return f"MATERIAL: {self.number}, {elements}"

    def _get_material_elements(self):
        sortable_components = [
            (iso, component.fraction)
            for iso, component in self.material_components.items()
        ]
        sorted_comps = sorted(sortable_components)
        elements_set = set()
        elements = []
        for isotope, _ in sorted_comps:
            if isotope.element not in elements_set:
                elements_set.add(isotope.element)
                elements.append(isotope.element.name)
        return elements

    def validate(self):
        if len(self.material_components) == 0:
            raise IllegalState(
                f"Material: {self.number} does not have any components defined."
            )

    def format_for_mcnp_input(self, mcnp_version):
        self.validate()
        ret = mcnp_object.MCNP_Object.format_for_mcnp_input(self, mcnp_version)
        if self.mutated:
            sorted_isotopes = sorted(list(self.material_components.keys()))
            first_component = self.material_components[sorted_isotopes[0]]

            ret.append(
                f"m{self.number:<8} {first_component.isotope.mcnp_str():>8} {first_component.fraction:>11.4g}"
            )
            for isotope in sorted_isotopes[1:]:  # skips the first
                component = self.material_components[isotope]
                ret.append(
                    f"{component.isotope.mcnp_str():>18} {component.fraction:>11.4g}"
                )
        else:
            ret = self._format_for_mcnp_unmutated(mcnp_version)
        if self.thermal_scattering:
            ret += self.thermal_scattering.format_for_mcnp_input(mcnp_version)
        return ret

    def __hash__(self):
        """WARNING: this is a temporary solution to make sets remove duplicate materials.

        This should be fixed in the future to avoid issues with object mutation:
            <https://eng.lyft.com/hashing-and-equality-in-python-2ea8c738fb9d>

        """
        temp_hash = ""
        sorted_isotopes = sorted(list(self.material_components.keys()))
        for isotope in sorted_isotopes:
            temp_hash = hash(
                (temp_hash, str(isotope), self.material_components[isotope].fraction)
            )

        return hash((temp_hash, self.number))

    def __eq__(self, other):
        return hash(self) == hash(other)
