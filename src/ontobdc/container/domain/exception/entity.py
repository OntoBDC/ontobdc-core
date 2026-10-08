class EntityRepositoryNotInjectedError(RuntimeError):
    """
    No repository for the data source of an entity was handed to the process
    that has to write it. OntoBDC ships no default one, so the process cannot
    guess where or how the entities are stored.
    """


class EntityFacadeNotFoundError(LookupError):
    """
    No facade is published for an entity type.
    """
