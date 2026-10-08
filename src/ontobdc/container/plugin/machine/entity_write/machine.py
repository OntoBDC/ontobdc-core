from __future__ import annotations

from typing import Any, Dict, List, Optional
from pathlib import Path

from sismic.exceptions import CodeEvaluationError

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.shared.adapter.loader import (
    CapabilityLoader,
    ResolverLoader,
)
from ontobdc.shared.adapter.worker import StateWorkerAdapter
from ontobdc.cli.domain.port.logger import LogRepositoryPort
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.adapter.capability import CapabilityExecutor
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.container.adapter.entity_dataset import EntityDatasets
from ontobdc.container.adapter.entity_facade import EntityFacadeLocator
from ontobdc.container.adapter.entity_linkset import EntityLinkset
from ontobdc.container.domain.exception.entity import EntityRepositoryNotInjectedError
from ontobdc.container.domain.model.entity_facade import EntityFacade
from ontobdc.container.domain.port.entity import EntityRepositoryPort
from ontobdc.container.plugin.machine.entity_write.port import (
    EntityWriteProcessStatePort,
    EntityWriteStateEvaluatorPort,
    EntityWriteStateTransitionHandlerPort,
)
from ontobdc.container.plugin.machine.entity_write.state import (
    EntityWriteProcessState,
)
from ontobdc.container.plugin.machine.entity_write.statechart import (
    EntityWriteStatechart,
)


class EntityWriteRequest:
    """
    The context keys the writing of entities reads and sets.

    The caller (the model of the entity) hands over where the container is,
    which entity it writes, the repository that keeps the rows, the rows and
    the documents they were made on. The process leaves the dataset it
    resolved under ``DATASET_PATH_KEY``.
    """

    CONTAINER_PATH_KEY: str = "container_path"
    ENTITY_IRI_KEY: str = "dataset_entity_iri"
    REPOSITORY_KEY: str = "entity_repository"
    RECORDS_KEY: str = "entity_records"
    SOURCE_DOCUMENTS_KEY: str = "entity_source_documents"
    DATASET_PATH_KEY: str = "dataset_path"

    @classmethod
    def repository(cls, context: CliContextPort) -> EntityRepositoryPort:
        """
        Raises:
            EntityRepositoryNotInjectedError: the caller handed no repository,
                or something that is not one. There is no default.
        """
        repository: Any = context.get_parameter_value(cls.REPOSITORY_KEY)
        if not isinstance(repository, EntityRepositoryPort):
            raise EntityRepositoryNotInjectedError(
                f"The context carries no entity repository under "
                f"'{cls.REPOSITORY_KEY}', and OntoBDC has no default one."
            )

        return repository

    @classmethod
    def container_path(cls, context: CliContextPort) -> Path:
        return Path(cls._text(context, cls.CONTAINER_PATH_KEY)).expanduser().resolve()

    @classmethod
    def entity_iri(cls, context: CliContextPort) -> str:
        return cls._text(context, cls.ENTITY_IRI_KEY)

    @classmethod
    def dataset_path(cls, context: CliContextPort) -> Path:
        return Path(cls._text(context, cls.DATASET_PATH_KEY)).expanduser().resolve()

    @classmethod
    def records(cls, context: CliContextPort) -> List[Dict[str, Any]]:
        records: Any = context.get_parameter_value(cls.RECORDS_KEY)
        if not isinstance(records, list) or not all(
            isinstance(record, dict) for record in records
        ):
            raise ValueError(
                f"'{cls.RECORDS_KEY}' must be a list of rows, each a mapping."
            )

        return records

    @classmethod
    def source_documents(cls, context: CliContextPort) -> List[str]:
        documents: Any = context.get_parameter_value(cls.SOURCE_DOCUMENTS_KEY)
        if documents is None:
            return []
        if not isinstance(documents, list) or not all(
            isinstance(document, str) and document.strip() for document in documents
        ):
            raise ValueError(
                f"'{cls.SOURCE_DOCUMENTS_KEY}' must be a list of document IRIs."
            )

        return documents

    @staticmethod
    def is_stored(
        record: Dict[str, Any],
        stored: Optional[Dict[str, str]],
        columns: Optional[List[str]] = None,
    ) -> bool:
        """
        Whether the stored row is the record: the same text in every column,
        a column the record leaves out being empty.
        """
        if stored is None:
            return False

        column: str
        for column in columns if columns is not None else list(stored):
            value: Any = record.get(column)
            if (stored.get(column) or "") != ("" if value is None else str(value)):
                return False

        return True

    @staticmethod
    def _text(context: CliContextPort, key: str) -> str:
        value: Any = context.get_parameter_value(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Required parameter is missing: {key}")

        return value.strip()


class EntityWriteStateEvaluatorAdapter(EntityWriteStateEvaluatorPort):
    """
    Reads the dataset and its data source and reports how far the writing of
    the entities already is.

    Each state holds when the one before it holds and its own condition on
    disk does; the first that does not is where the writing stands.
    """

    def evaluate(
        self,
        context: CliContextPort,
    ) -> EntityWriteProcessStatePort:
        repository: EntityRepositoryPort = EntityWriteRequest.repository(context)
        dataset_path: Optional[Path] = EntityDatasets.first(
            EntityWriteRequest.container_path(context),
            EntityWriteRequest.entity_iri(context),
        )
        if dataset_path is None:
            return EntityWriteProcessState.UNDEFINED
        context.set_parameter_value(
            EntityWriteRequest.DATASET_PATH_KEY, str(dataset_path)
        )

        if not repository.data_source_exists(dataset_path):
            return EntityWriteProcessState.DATASET_FOUND

        facade: EntityFacade = EntityFacadeLocator.of(
            EntityWriteRequest.entity_iri(context)
        )
        if not set(facade.column_names()) <= set(repository.columns(dataset_path)):
            return EntityWriteProcessState.DATA_SOURCE_AVAILABLE

        stored: Dict[str, Dict[str, str]] = repository.rows(dataset_path)
        record: Dict[str, Any]
        for record in EntityWriteRequest.records(context):
            if not EntityWriteRequest.is_stored(
                record, stored.get(str(record.get("global_id")))
            ):
                return EntityWriteProcessState.DATA_SOURCE_COLUMNS_SYNCED

        linkset: EntityLinkset = EntityLinkset(
            dataset_path, repository.data_source_path(dataset_path)
        )
        if not linkset.path.is_file() or not set(
            EntityWriteRequest.source_documents(context)
        ) <= set(linkset.links()):
            return EntityWriteProcessState.DATA_SOURCE_FILLED

        return EntityWriteProcessState.ENTITY_DOCUMENTS_LINKED


class EntityWriteStateTransitionHandler(EntityWriteStateTransitionHandlerPort):
    def __init__(
        self,
        context: CliContextPort,
        logger: Optional[LogRepositoryPort] = None,
    ) -> None:
        # Fails before anything runs when there is no repository to write to.
        EntityWriteRequest.repository(context)

        self._context: CliContextPort = context
        self._logger: LogRepositoryPort = logger or NullLogRepository()
        self._state_evaluator: EntityWriteStateEvaluatorPort = (
            EntityWriteStateEvaluatorAdapter()
        )
        self._active_state: Optional[EntityWriteProcessStatePort] = None
        self._observed_state: Optional[EntityWriteProcessStatePort] = None

    @property
    def current_state(self) -> EntityWriteProcessStatePort:
        if self._active_state is not None:
            return self._active_state

        return self.observed_state

    @property
    def observed_state(self) -> EntityWriteProcessStatePort:
        """
        The state the writing is in on disk, read once per machine step and
        held until something can have changed it.
        """
        if self._observed_state is None:
            self._observed_state = self._state_evaluator.evaluate(self._context)

        return self._observed_state

    def can_transit_to(self, to_state: EntityWriteProcessStatePort) -> bool:
        active_state: EntityWriteProcessStatePort = self.current_state
        if active_state == EntityWriteProcessState.UNDEFINED:
            return to_state == EntityWriteProcessState.DATASET_FOUND

        return active_state != to_state

    def perform_state_transition(
        self, to_state: EntityWriteProcessStatePort
    ) -> None:
        if self.observed_state == to_state:
            return

        self._logger.log_info(
            f"Entity write transition: {self.current_state.value} -> {to_state.value}",
        )
        capability_id: str = (
            "org.ontobdc.container.plugin.capability.transformation.target."
            f"{to_state.value.strip('_')}"
        )
        capability_type: Any = CapabilityLoader().get(capability_id)
        if capability_type is None:
            raise ValueError(f"Entity write capability not found: {capability_id}")

        capability: CapabilityPort = capability_type()
        try:
            CapabilityExecutor.execute(
                capability,
                self._context,
                StrategyParamResolver(ResolverLoader()),
            )
        finally:
            self._observed_state = None

    def validate_state_transition(
        self,
        from_state: EntityWriteProcessStatePort,
        to_state: EntityWriteProcessStatePort,
    ) -> bool:
        if from_state == to_state:
            return False

        state_sequence: List[str] = EntityWriteStatechart.sequence()
        observed_name: str = self.observed_state.value.strip("_")
        target_name: str = to_state.value.strip("_")
        if observed_name not in state_sequence and observed_name != "undefined":
            raise ValueError(
                f"Observed state '{observed_name}' is absent from the entity "
                "write statechart."
            )
        if target_name not in state_sequence:
            raise ValueError(
                f"Target state '{target_name}' is absent from the entity "
                "write statechart."
            )
        if observed_name == "undefined":
            return False

        return state_sequence.index(observed_name) >= state_sequence.index(target_name)

    def execute(self) -> CommandResponse:
        worker: StateWorkerAdapter = StateWorkerAdapter(
            state_adapter=EntityWriteProcessState,
            state_context_name="EntityWriteProcessStatePort",
            handler=self,
            logger=self._logger,
            statechart_file_path=EntityWriteStatechart.path(),
        )
        try:
            visited_states: List[str] = worker.work()
        except CodeEvaluationError as error:
            # The statechart wraps whatever its actions raise; the caller
            # needs the error itself, such as a repository that is missing.
            if isinstance(error.__cause__, Exception):
                raise error.__cause__ from None
            raise
        return CommandResponse(
            title="Entities Written",
            description="The entities are in the data source of their dataset, linked to the documents they were made on.",
            content={
                "dataset_path": str(EntityWriteRequest.dataset_path(self._context)),
                "current_state": self.current_state.value,
                "visited_states": visited_states,
            },
        )

    def bind_active_state(self, state: EntityWriteProcessStatePort) -> None:
        self._active_state = state
