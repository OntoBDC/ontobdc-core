from ontobdc.shared.domain.model.shacl import ShaclValidationReport


class ShaclConformanceError(ValueError):
    """A data graph that does not conform to the shapes it must satisfy."""

    def __init__(self, subject: str, report: ShaclValidationReport) -> None:
        self.report: ShaclValidationReport = report
        details: str = "\n".join(
            f"  - {violation.describe()}" for violation in report.violations
        )
        super().__init__(
            f"{subject} does not conform to its SHACL shapes "
            f"({len(report.violations)} violations):\n{details}"
        )
