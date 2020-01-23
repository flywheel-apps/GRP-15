#!/usr/bin/env python3


import os
import json
import glob2
import tempfile
import shutil
import flywheel
import zipfile
import logging
from pprint import pprint as pp

log = logging.getLogger("GRP-15")


def create_archive(content_dir, arcname, zipfilepath=None):
    """Generae an archive from a given directory.

    Args:
        content_dir (str): Full path to directory containing archive content.
        arcname (str): Name for top-level folder in archive.
        zipfilepath (str): Desired path of output archive. If not provided the
                           content_dir basename will be used. Defaults to None.

    Returns:
        str: Full path to created zip archive.

    """

    import zipfile

    if not zipfilepath:
        zipfilepath = content_dir + '.zip'
    with zipfile.ZipFile(zipfilepath, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        zf.write(content_dir, arcname)
        for fn in os.listdir(content_dir):
            zf.write(os.path.join(content_dir, fn), os.path.join(os.path.basename(arcname), fn))
    return zipfilepath


def extract_archive(zip_file_path, extract_location):
    """Extract zipfile to <zip_file_path> and return the path to the directory containing the files,
    which should be the zipfile name without the zip extension.

    Args:
        zip_file_path (str): Full path to existing archive.
        extract_location (str): Full path of top-level destination for extraction.

    Returns:
        str: Path to extracted archive

    """

    if not zipfile.is_zipfile(zip_file_path):
        log.warning('{} is not a Zip File!'.format(zip_file_path))
        return None

    with zipfile.ZipFile(zip_file_path) as ZF:
        if '/' in ZF.namelist()[0]:
            extract_dest = os.path.join(extract_location, ZF.namelist()[0].split('/')[0])
            ZF.extractall(extract_location)
            return extract_dest
        else:
            extract_dest = os.path.join(extract_location, os.path.basename(zip_file_path).split('.zip')[0])
            if not os.path.isdir(extract_dest):
                log.debug('Creating extract directory: {}'.format(extract_dest))
                os.mkdir(extract_dest)
            log.debug('Extracting {} archive to: {}'.format(zip_file_path, extract_dest))
            ZF.extractall(extract_dest)

            return extract_dest


def generate_project_template(gear_context, project, outname=None):
    """For a given project generate a dict with permissions and gear rules.

    Args:
        gear_context (:obj:flywheel.gear_context.GearContext): Flywheel Gear
            Context
        project (:obj: flywheel.models.project.Project): Flywheel Project which
            has the existing permissions and gear rules.
        outname (str): Full path to output the json file contianing the template.
            If not provided we default to `/flywheel/v0/output/project_template.json`

    Returns:
        dict: Project template containing 'permissions', and 'rules':
            {
              "permissions": [
                {
                  "id": "<user_id>",
                  "access": "<access_rights>"
                }
              ],
              "rules": [
                {
                  "project_id": "<project_id>",
                  "gear_id": "<gear_id>",
                  "name": "<gear_name>",
                  "config": {},
                  "fixed_inputs": [
                    {
                      "type": "project",
                      "id": "<container_id>",
                      "name": "<file_name>",
                      "input": "<input_name>"
                    }
                  ],
                  "auto_update": false,
                  "any": [],
                  "all": [
                    {
                      "type": "file.type",
                      "value": "dicom",
                      "regex": false
                    }
                  ],
                  "_not": [],
                  "disabled": true,
                  "compute_provider_id": null,
                  "id": null
                }
              ]
            }
    """

    fw = gear_context.client

    if not outname:
        outname = os.path.join(gear_context.output_dir, 'project-settings_template_{}.json'.format(project.id))

    template = dict()
    template['rules'] = list()

    log.info(f'Generating template from source project: {project.group}/{project.label} [id={project.id}]')

    rules = [ r.to_dict() for r in fw.get_project_rules(project.id) ]
    template['permissions'] = [ p.to_dict() for p in project.permissions ]

    for rule in rules:
        # Here we grab the gear info for easy lookup later on. Note that it will
        # be removed.
        rule['gear'] = fw.get_gear(rule['gear_id']).gear.to_dict()
        template['rules'].append(rule)

    save_template(template, outname)

    return template


def save_template(template, outfilename):
    """Write project template to JSON file.

    Args:
        template (dict): Template dictionary, created by generate_project_template
        outfilename (str): Full path for output file.

    Returns:
        str: Full path to generated template json.

    """

    with open(outfilename, 'w') as of:
        json.dump(template, of, sort_keys=True, indent=4, separators=(',', ': '))

    return outfilename


def download_fixed_inputs(gear_context, template, project_id):
    """For each fixed input found in the templates gear rules, download the file
       and create an archive from those files within the outdir specified by the
       gear_context. The resulting archive can then be loaded to a new project.

    Args:
        gear_context (:obj:flywheel.gear_context.GearContext): Flywheel Gear
            Context
        template (dict): Project tempalte dictionary, containing a list of project
            "permissions" and a list of project "rules".
        project_id (string): Source project ID (used for naming the output archive.)

    Returns:
        str: Full path to generated fixed input archive.

    """

    fw = gear_context.client
    outdir = gear_context.output_dir

    tdirpath = tempfile.mkdtemp()

    # Create the archive directory, which will be zipped
    content_dir = os.path.join(tdirpath, 'project-settings_fixed-inputs_{}'.format(project_id))
    os.mkdir(content_dir)

    downloaded = list() # List of files that are to be downloaded

    log.info('Checking template for fixed inputs...')
    for rule in template['rules']:
        if rule.get('fixed_inputs'):
            for fixed_input in rule.get('fixed_inputs'):
                container = fw.get(fixed_input.get('id'))
                fname = fixed_input.get('name')
                container.download_file(fname, os.path.join(content_dir, fname))
                downloaded.append(fname)

    if downloaded:
        archive_name = os.path.join(outdir, os.path.basename(content_dir) + '.zip')
        log.info(f'Saved {len(downloaded)} fixed input files. Creating archive {archive_name}')
        create_archive(content_dir, os.path.basename(content_dir), archive_name)
    else:
        log.info(f'Found {len(downloaded)} fixed input files.')
        archive_name = None

    shutil.rmtree(tdirpath)

    return archive_name


def create_project(gear_context):
    """Create project specified in config.clone_project_path. If an existing
        project is found (and config.apply_to_existing_project flag is set to
        True) it will be returned.

    Args:
        gear_context (:obj:flywheel.gear_context.GearContext): Flywheel Gear
            Context

    Returns:
        :obj:flywheel.models.project.Project: Flywheel Project to which the
            template permissions and rules will be applied.

    """

    fw = gear_context.client

    clone_project_path = gear_context.config.get('clone_project_path').split('/')

    group_id = clone_project_path[0]
    project_label = clone_project_path[1]

    # Check for existing project
    try:
        project = fw.lookup(f'{group_id}/{project_label}')
        if gear_context.config.get('apply_to_existing_project') and project:
            log.info(f'Existing project {group_id}/{project_label} (id={project.id}) found! apply_to_existing_project flag is set... the template will be applied to this project!')
            return fw.get_project(project.id)
        else:
            log.warning(f'Project {group_id}/{project_label} (id={project.id}) found! apply_to_existing_project flag is False, bailing out!')
            os._exit(1)
    except:
        pass

    log.info(f'Creating new project: group={group_id}, label={project_label}')
    try:
        project_id = fw.add_project({'group': group_id, "label": project_label})
        project = fw.get_project(project_id)
        log.info(f'Done. Created new project: group={group_id}, label={project_label}, id={project.id}')

    except flywheel.ApiException as err:
        log.error(f'API error during project creation: {err.status} -- {err.reason}')
        os._exit(1)

    return project


def upload_fixed_inputs(fixed_input_archive, project):
    """Unpack the fixed inputs archive and upload to the clone project.

    Args:
        fixed_input_archive (str): Full path to `fixed_input_archive`.
        project (:obj: flywheel.models.project.Project): Flywheel Project to which
            the fixed_inputs will be uploaded.

    Returns:
        The return value. True for success, False otherwise.

    """

    tdirpath = tempfile.mkdtemp()

    fixed_input_dir = extract_archive(fixed_input_archive, tdirpath)

    # Get file paths from the input dir
    fixed_inputs = glob2.glob(fixed_input_dir + '/*', recursive=True)

    # Upload each of the fixed inputs to the clone project.
    for fixed_input in fixed_inputs:
        log.info(f'Uploading fixed input file: {os.path.basename(fixed_input)}')
        project.upload_file(fixed_input)

    log.debug(f'Deleting {fixed_input_dir}')

    shutil.rmtree(tdirpath)

    return True


def apply_template_to_project(gear_context, project, template, fixed_input_archive=None):
    """Apply <template> permissions and gear rules to <project>.

    Args:
        gear_context (:obj:flywheel.gear_context.GearContext): Flywheel Gear
            Context
        project (:obj: flywheel.models.project.Project): Flywheel Project to which
            the rules and permissions will be applied.
        template (dict): Project tempalte dictionary, containing a list of project
            "permissions" and a list of project "rules".
        fixed_input_archive (str, optional): Path to archive containing gear
            rule fixed inputs. Defaults to None.

    Returns:
        The return value. True for success, False otherwise.

    """

    fw = gear_context.client

    # Permissions
    if gear_context.config.get('permissions') and template.get('permissions'):
        log.info('APPLYING PERMISSIONS TO PROJECT...')
        users = [ x.id for x in project.permissions ]
        for permission in template['permissions']:
            if permission['id'] not in users:
                log.info(' Adding {} to {}'.format(permission['id'], project.label))
                project.add_permission(flywheel.Permission(permission['id'], permission['access']))
            else:
                log.debug(' {} already has permissions in {}'.format(permission['id'], project.label))
        log.info('...PERMISSIONS APPLIED')
    else:
        log.info('NOT APPLYING PERMISSIONS TO PROJECT!')


    # Handle Fixed Inputs
    if gear_context.config.get('gear_rules') and template.get('rules'):
        log.info('APPLYING GEAR RULES TO PROJECT...')
        if fixed_input_archive:
            log.info('Unpacking and uploading fixed gear inputs...')
            upload_fixed_inputs(fixed_input_archive, project)
            log.info('...Done.')


        # Gear Rules
        gear_rules = list()
        for rule in template['rules']:
            log.info(' Generating new rule from tempalte: {}'.format(rule['name']))
            try:
                # If the gear does not exist, we are probably on another instance and
                # need to look it up.
                log.info('Locating gear {}...'.format(rule['gear_id']))
                gear = fw.get_gear(rule['gear_id'])
                log.info('Found {},{}:{}'.format(rule['gear_id'], rule['gear']['name'], rule['gear']['version']))
            except:
                log.warning('Gear ID {} cannot be found on this system!'.format(rule['gear_id']))
                try:
                    log.info('Checking for the gear locally...')
                    gear = fw.lookup('gears/{}/{}'.format(rule['gear']['name'], rule['gear']['version']))
                    rule['gear_id'] = gear.id
                except:
                    log.error('{}:{} was not found on this system! Please install it!'.format(rule['gear']['name'], rule['gear']['version']))
                    log.warning('Skipping this rule! {}'.format(rule['name']))
                    continue

            rule['project_id'] = project.id
            rule['id'] = None
            if 'gear' in rule:
                del rule['gear']

            # For each fixed input, fix the project id
            if rule['fixed_inputs']:
                for fi in range(0, len(rule['fixed_inputs'])):
                    rule['fixed_inputs'][fi]['id'] = project.id
                    rule['fixed_inputs'][fi]['type'] = "project"
                    if not rule['fixed_inputs'][fi]['base']:
                        del rule['fixed_inputs'][fi]['base']
                    if not rule['fixed_inputs'][fi]['found']:
                        del rule['fixed_inputs'][fi]['found']

            # Fix all and any fields
            if rule['all']:
                for ar in range(0, len(rule['all'])):
                    if not rule['all'][ar]['regex']:
                        rule['all'][ar]['regex'] = False
            if rule['any']:
                for ar in range(0, len(rule['any'])):
                    if not rule['any'][ar]['regex']:
                        rule['any'][ar]['regex'] = False
            if rule['_not']:
                log.debug('RULE NOT')
                for ar in range(0, len(rule['_not'])):
                    if not rule['_not'][ar]['regex']:
                        log.debug('setting to false...')
                        rule['_not'][ar]['regex'] = False

            # Forumlate the gear_rule
            gear_rules.append(flywheel.models.rule.Rule(project_id=project.id,
                                                 gear_id=rule['gear_id'],
                                                 name=rule['name'],
                                                 config=rule['config'],
                                                 fixed_inputs=rule['fixed_inputs'],
                                                 auto_update=rule['auto_update'],
                                                 any=rule['any'],
                                                 all=rule['all'],
                                                 _not=rule['_not'],
                                                 disabled=rule['disabled']))

        project_rules = [x for x in fw.get_project_rules(project.id)]
        project_rule_names = [x.name for x in fw.get_project_rules(project.id)]
        log.debug(project_rule_names)
        RULE_ACTION = gear_context.config.get('existing_rules')

        for gear_rule in gear_rules:
            if gear_rule.get('name') in project_rule_names:
                log.warning('A matching rule for \'{}\' was already found on this project.'.format(gear_rule.get('name')))
                matching_rule = [ x for x in fw.get_project_rules(project.id) if x.name == gear_rule.get('name') ]
                if RULE_ACTION == "REPLACE":
                    for mr in matching_rule:
                        log.info('REPLACE action was configured. Deleting the matching rule.')
                        fw.remove_project_rule(project.id, mr.id)
                elif RULE_ACTION == "SKIP":
                    log.info('SKIP action was configured. Not adding rule from template.')
                    continue
                elif RULE_ACTION == "APPEND":
                    log.warning('APPEND action was configured. Template rule will be added - duplicates will exist.')
            try:
                log.info('Adding "{}" rule to "{} (id={})" project'.format(gear_rule['name'], project.label, project.id))
                fw.add_project_rule(project.id, gear_rule)
            except flywheel.ApiException as err:
                log.error(f'API error during gear rule creation: {err.status} -- {err.reason} -- {err.detail}. \nBailing out!')
                log.debug(gear_rule)
                os._exit(1)
        log.info('...GEAR RULES APPLIED TO PROJECT!')
    else:
        log.info('NOT APPLYING GEAR RULES TO PROJECT! (config.gear_fules=False)')

    return True


def get_valid_project(gear_context):
    """Use the <gear_context> to parse the destination and use it to determine
        a vaild project. The destination should be an analysis, and the parent of
        that analysis container must be a project. That project is returned here.

    Args:
        gear_context (:obj:flywheel.gear_context.GearContext): Flywheel Gear
            Context
    Returns:
        :obj:flywheel.models.project.Project: Flywheel Project which has the
            existing permissions and gear rules.

    """

    if gear_context.destination['type'] != "analysis":
        msg = 'Destination must be an analysis!'
        log.error(msg)
        os._exit(1)

    analysis = gear_context.client.get_analysis(gear_context.destination['id'])

    try:
        project = gear_context.client.get_project(analysis.parent['id'])
    except flywheel.ApiException as err:
        log.error(f'Could not retrieve source project. This Gear must be run at the project level!: {err.status} -- {err.reason}. \nBailing out!')
        os._exit(1)

    return project


def load_template_from_input(template_file):
    """Load json template from file.

    Args:
        template_file (str): Full path to JSON template file.

    Returns:
        dict: Project template containing 'permissions', and 'rules':
            {
              "permissions": [],
              "rules": []
            }

    """

    log.info(f'Loading existng template file: {template_file}')
    with open(template_file, 'r') as tf:
        template = json.load(tf)

    return template


if __name__ == "__main__":

    APPLY_TEMPLATE = True # This variable controls the application of the template.
                          # When this is not true - because there is no clone
                          # project or input provided - only the template
                          # and fixed input archive will be generated.

    with flywheel.gear_context.GearContext() as gear_context:

        gear_context.init_logging()
        log.setLevel(gear_context.config['gear-log-level'])
        log.info('Destination: {}'.format(gear_context.destination))
        log.info('Config: {}'.format(gear_context.config))

        source_project = get_valid_project(gear_context)

        # If the user has supplied a template then we load from file, otherwise
        # we generate from the source project.
        if gear_context.get_input_path('template'):
            template = load_template_from_input(gear_context.get_input_path('template'))
            APPLY_FROM_INPUT = True
        else:
            template = generate_project_template(gear_context, source_project)
            APPLY_FROM_INPUT = False

        if gear_context.config.get('gear_rules'):
            if gear_context.get_input_path('fixed_inputs'):
                fixed_input_archive = gear_context.get_input_path('fixed_inputs')
            else:
                fixed_input_archive = download_fixed_inputs(gear_context, template, source_project.id)

        if gear_context.config.get('clone_project_path'):
            # If a clone_project_path was provided, attempt to create the project,
            # or find an existing project and return it.
            clone_project = create_project(gear_context)
        elif APPLY_FROM_INPUT:
            # If the input template was already provided then the clone_projet
            # is the source_project
            log.info('Applyting template from input. Setting clone project to source.')
            clone_project = source_project
        else:
            # We're just exporting a template.
            log.info('Exporting template... Done!')
            APPLY_TEMPLATE = False

        if APPLY_TEMPLATE:
            apply_template_to_project(gear_context, clone_project, template, fixed_input_archive)

    log.info('Done!')
    os._exit(0)
