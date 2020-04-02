# GRP-15:  Project Settings Import and Export

For a given project, clone the gear rules and (optionally) permissions to a project, or export the settings for import to another instance/project.

## Motivation
For new projects it can be difficult to replicate existing project configurations. This Gear will run at the project level and generate a new project (locally or via configuration file for external use) with the appropriate gear rules and user permissions.

## Inputs
``` json
{
  "template": {
    "base": "file",
    "description": "Template json file from source project. If this is provided to this gear at runtime, the template will be applied to this project.",
    "optional": true,
    "type": {
      "enum": [
        "source code"
      ]
    }
  },
  "fixed_inputs": {
    "base": "file",
    "description": "Archive containing fixed input files. These files will be uploaded to the cloned project and referenced by the gear rules. If this is provided to this gear at runtime, the files will be applied to this project.",
    "optional": true,
    "type": {
      "enum": [
        "archive"
      ]
    }
  }
}
```

## Configuration
```json
{
  "clone_project_path": {
    "optional": true,
    "description": "Path for new project to be created. Format should be <group_id>/<project_name>. If <clone_project_path> provided a new project will be created. If the project exists, the 'apply_to_existing_project' option must be used to update the project settings. If this option is omitted settings will be exported.",
    "type": "string",
    "pattern": "^[a-z0-9\\-]+/.+$"
  },
  "permissions": {
    "default": false,
    "description": "Export permissions from origin project and/or import those permissions to the clone project.",
    "type": "boolean"
  },
  "default_group_permissions": {
    "default": true,
    "description": "Applies the clone project's default group permissions to the clone project. This is done by default and will override permissions within the template. If you wish to use the permissions within the template you must set `apply_group_permissions` to `false`, and `permissions` to `true`.",
    "type": "boolean"
  },
  "gear_rules": {
    "default": true,
    "description": "Export/Import Gear Rules and related fixed inputs (if applicable).",
    "type": "boolean"
  },
  "apply_to_existing_project": {
    "default": true,
    "description": "If a project already exists, apply settings and rules to that project.",
    "type": "boolean"
  },
  "existing_rules": {
    "default": "REPLACE",
    "description": "If a project already has a rule with the same name as a template rule, this option will determine what happens with those rules. Options are: 'REPLACE' (replace the existing rule with the tempalte rule), 'APPEND' (add template rule - may result in duplicate rules), 'SKIP' (don't add the matching tempalte rule).",
    "enum": [
      "REPLACE",
      "APPEND",
      "SKIP"
    ],
    "type": "string"
  },
  "gear-log-level": {
    "default": "INFO",
    "description": "Gear Log verbosity level (ERROR|WARNING|INFO|DEBUG)",
    "type": "string",
    "enum": [
      "ERROR",
      "WARNING",
      "INFO",
      "DEBUG"
    ]
  }
}
```

## Outputs

1. `project_template_<source_project_id>.json` - Project template JSON file.
2. `fixed_inputs_<source_project_id>.zip` - An archive consisting of any files referenced by the exported gear rules (if applicable).

## Usage
Note that by default `apply_group_permissions` is `true`, which will cause the default group permissions of the clone project to be set upon that project - functionally ignoring any permissions found within the template. If you wish to use the permissions within the template you must set `apply_group_permissions` to `false`, and `permissions` to `true`.

#### Exporting Project Settings - without Project Creation
To export a project's settings (permissions and gear rules):
1. Run GRP-15 as a project analysis on the source project without configuring a `clone_project_path`. This will not create a project, nor apply any settings. It will simply generate the settings output files.

#### Exporting Project Settings - with Project Creation
To export a project's settings (permissions and gear rules), create a new project, and apply those settings to the new project
1. Run GRP-15 as a project analysis on the source project
1. Configure a `clone_project_path`. This will trigger the creation of a new project.
1. Check `permissions` and `gear_rules` configuration options as desired. _Default for both is true_.

#### Import Project Settings to an Existing Project
To import project settings from one project to another:
1. _Generate settings files:_  Run GRP-15 as a project analysis on the source project without configuring a `clone_project_path`. This will not create a project, nor apply any settings. It will simply generate the settings output files. _Optionally you can use files from an existing run._
1. _Upload settings files:_ Settings files should be uploaded to the target project as project attachments.
1. _Run_ GRP-15 as a project-level analysis on the _target project_, where you want the permissions and rules applied.
1. _Choose input files_ from the project attachments as appropriate for input to GRP-15.
