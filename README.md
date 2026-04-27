# KAT – Klipper Automation Toolkit

Advanced macro toolkit for Klipper and Kalico with hardware-aware automation and smart workflows.

---

## Overview

KAT is a modular macro system designed to extend and enhance Klipper-based printers.
It focuses on **automation, reliability, and adaptability** by making macros aware of the printer’s actual configuration.

Instead of static macros, KAT dynamically adapts to available features such as:

* Beacon probing
* Quad Gantry Leveling (QGL)
* Z Tilt Adjust
* Bed Mesh
* Toolhead and hardware configuration

This allows a single macro set to work across multiple machines without constant rewriting.

---

## Key Features

* **Smart START_PRINT**

  * Automatically detects printer capabilities
  * Runs appropriate leveling and calibration routines
  * Optimized startup flow

* **Intelligent PAUSE / RESUME**

  * Stores and restores temperatures and fan states
  * Safe parking and resume behavior
  * Designed for real-world use, not just demos

* **Hardware-aware automation**

  * Adapts based on configured modules
  * Works with or without advanced sensors like Beacon

* **Modular structure**

  * One macro per file
  * Easy to include, modify, and extend

* **Cross-platform compatibility**

  * Works with standard Klipper
  * Fully compatible with Kalico
  * Designed to be independent of specific distributions

---

## Project Structure

```text
macros/
    start_print/
    end_print/
    pause_resume/
    calibration/
    hardware/

templates/
    example printer configurations

docs/
    documentation and usage guides
```

---

## Installation (WIP)

Instructions will be added as the project matures.

Planned approach:

1. Copy relevant macro files into your Klipper config
2. Include them in your `printer.cfg`
3. Adjust variables to match your hardware

---

## Philosophy

KAT is built around a few core principles:

* **Write once, run anywhere**
  Macros should adapt to the machine, not the other way around.

* **Readable and maintainable**
  Every macro is clearly structured and thoroughly commented.

* **Real-world reliability**
  Designed for production environments, not just test setups.

* **Modularity over monoliths**
  Small, focused components instead of large all-in-one configs.

---

## Roadmap

* Smart START_PRINT (baseline)
* Advanced PAUSE/RESUME system
* Z skip detection and calibration tools
* Input shaper helpers
* Auto-configuration layer
* Extended hardware abstraction

---

## Contributing

This project is in early development.
Structure and core functionality are being defined.

Contributions, ideas, and feedback are welcome as the system evolves.
