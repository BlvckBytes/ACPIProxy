# ACPIProxy

Automatically generate the required OpenCore ACPI patches as well as a template SSDT to proxy re-route method calls.

🧨 WARNING: This repo is still WIP, the tool is **not** yet working!

## Table Of Contents

* [Usage](#usage)
* [Example](#example)
  * [Patches](#patches)
  * [Add](#add)
  * [SSDT](#ssdt)

## Usage

There are two modes for this tool, nameley: `generate` and `undo`. `generate` will add the ACPI patches to your `config.plist` if not yet existing as well as create/update the matching SSDT, and `undo` will remove all changes made by ACPIProxy.

```bash
python acpiproxy.py generate <Pattern> <Path-To-OC-Folder> <Path-To-DSDT.aml>
```

```bash
python acpiproxy.py undo <Pattern> <Path-To-OC-Folder>
```

Where the pattern has to be 4 characters in total, including wildcards (don't try to add too much meaning to their corresponding symbols... it's rather arbitrary):
* \+ => any number
* ! => any number or _
* \- => any letter
* @ => any letter or _
* ? => any number or letter
* \* => any number or letter or _

For example, `_Q+!` would match all available EC-Queries and proxy them. `+` for a number, and `!` for a number or a underscore, as this also matches `_Q0` through `_Q9`, which in reality have a trailing underscore.

The path to your OC folder could look something like this: `/Volumes/EFI/EFI/OC`. In order to find the proper method definitions and create patches for them, the tool needs your DSDT as assembled machine language (aml). Dump it by booting clover and hitting F4 on your keyboard. Then, just provide an absolute path as the third argument, like: `/Users/blvckbytes/Desktop/origin/DSDT.aml`.

## Example

Let's see how one would proxy all EC Query methods. They have the format of: `_QXX`, where XX can be any two numbers. Thus, the pattern is: `_Q++`. An invocation would look the following:

```bash
python acpiproxy.py generate '_Q++' /Volumes/EFI/EFI/OC /Users/blvckbytes/Desktop/origin/DSDT.aml
```

It will generate two parts, ACPI patches in `config.plist` under ACPI/Patch with an entry in ACPI/Add for the SSDT, as well as the SSDT in `/Volumes/EFI/EFI/OC/ACPI`, named like this: `SSDT-_Q++.aml`.

My DSDT only has a single EC query, which is why it makes for a pretty good example:

### Patches

### Add

### SSDT