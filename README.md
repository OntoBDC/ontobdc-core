# OntoBDC

> OntoBDC is a domain-driven data architecture for engineering systems.

OntoBDC provides a structured way to define capabilities, actions, and use cases over engineering data.

<p align="left">
  <img src="./images/ontobdc_colab_example_02.png" width="55%" />
</p>

It enables reproducible, auditable, and automation-ready workflows across technical domains.

## Used by

OntoBDC is currently used as the core data and execution layer of:

- <a href="https://infobim.org" target="_blank" rel="noopener noreferrer">InfoBIM</a>

InfoBIM leverages OntoBDC to define capabilities, execute checks, and orchestrate engineering data workflows.

## 🚀 Getting started

Install the package:

```sh
pip install ontobdc
```

After installation, the `ontobdc` CLI becomes available:

```sh
ontobdc --help
```

From there, you can execute checks, run capabilities, and interact with registered use cases.

## 🧪 Checking

The `check` command validates engineering data against defined capabilities and rules.

```sh
ontobdc check --repair
```

It executes registered checks over the target dataset, reports inconsistencies, and optionally applies automated repairs when `--repair` is enabled.

<p align="left">
  <img src="./images/ontobdc_colab_example_01.png" width="55%" />
</p>

This ensures reproducibility, auditability, and deterministic validation of engineering workflows.

## 📄 License

Licensed under **Apache 2.0**.
