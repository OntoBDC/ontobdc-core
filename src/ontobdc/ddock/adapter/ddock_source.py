from typing import ClassVar, List


class DdockSource:
    """
    What of the source folder of the ddock zip becomes the application. The
    rest of it (tests, tooling of development) is not needed to build or to
    run the application, so it is left out.
    """

    INCLUDE: ClassVar[List[str]] = [
        "asset",
        "ontobdc",
        "python",
        "scripts",
        "index.html",
        "package.json",
        "package-lock.json",
        "tsconfig.json",
        "vite.config.ts",
    ]
