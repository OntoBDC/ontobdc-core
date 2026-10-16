from importlib import import_module
from typing import ClassVar, Dict


class ValueGenerators:
    """
    The value generators a facade can name as the default of a field, found by
    their IRI. Each one is a file of ``adapter/generator``; a generator that is
    not in the table cannot be run, and asking for it is an error, not a
    silent blank.
    """

    FACADE: ClassVar[str] = "http://datacenter.app.br/ontology/tool/ontobdc/facade/ns.ttl#"
    BY_IRI: ClassVar[Dict[str, str]] = {
        f"{FACADE}UuidGenerator": "ontobdc.container.adapter.generator.uuid_generator:UuidGenerator",
        f"{FACADE}CurrentDateTimeGenerator": "ontobdc.container.adapter.generator.current_datetime_generator:CurrentDateTimeGenerator",
    }

    @classmethod
    def generate(cls, iri: str) -> str:
        """
        The value the generator produces now.

        Raises:
            LookupError: no generator is registered for ``iri``.
        """
        target: str = cls.BY_IRI.get(iri, "")
        if not target:
            raise LookupError(f"No value generator is registered for <{iri}>.")

        module_name, class_name = target.split(":")
        return str(getattr(import_module(module_name), class_name).generate())
