        'wait_before', 'wait_after', 'pause_before', 'timeout',
        'with_items', 'keep_result', 'target', 'join'
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_serialization import jsonutils
import six
import yaml

from heat.common import exception
from heat.common.i18n import _
from heat.engine import attributes
from heat.engine import constraints
from heat.engine import properties
from heat.engine import resource
from heat.engine.resources import signal_responder
from heat.engine import support


class Workflow(signal_responder.SignalResponder,
               resource.Resource):

    support_status = support.SupportStatus(version='2015.1')

    default_client_name = 'mistral'

    entity = 'workflows'

    PROPERTIES = (
        NAME, TYPE, DESCRIPTION, INPUT, OUTPUT, TASKS, PARAMS, TASK_DEFAULTS,
        USE_REQUEST_BODY_AS_INPUT
    ) = (
        'name', 'type', 'description', 'input', 'output', 'tasks', 'params',
        'task_defaults', 'use_request_body_as_input'
    )

    _TASKS_KEYS = (
        TASK_NAME, TASK_DESCRIPTION, ON_ERROR, ON_COMPLETE, ON_SUCCESS,
        ACTION, WORKFLOW, PUBLISH, TASK_INPUT, REQUIRES, RETRY,
        WAIT_BEFORE, WAIT_AFTER, PAUSE_BEFORE, TIMEOUT,
        WITH_ITEMS, KEEP_RESULT, TARGET, JOIN
    ) = (
        'name', 'description', 'on_error', 'on_complete', 'on_success',
        'action', 'workflow', 'publish', 'input', 'requires', 'retry',
        'wait_before', 'wait_after', 'pause_before', 'timeout',
        'with_items', 'keep_result', 'target', 'join'
    )

    _TASKS_TASK_DEFAULTS = [
        ON_ERROR, ON_COMPLETE, ON_SUCCESS,
        REQUIRES, RETRY, WAIT_BEFORE, WAIT_AFTER, PAUSE_BEFORE, TIMEOUT
    ]

    _SIGNAL_DATA_KEYS = (
        SIGNAL_DATA_INPUT, SIGNAL_DATA_PARAMS
    ) = (
        'input', 'params'
    )

    ATTRIBUTES = (
        WORKFLOW_DATA, ALARM_URL, EXECUTIONS
    ) = (
        'data', 'alarm_url', 'executions'
    )

    properties_schema = {
        NAME: properties.Schema(
            properties.Schema.STRING,
            _('Workflow name.')
        ),
        TYPE: properties.Schema(
            properties.Schema.STRING,
            _('Workflow type.'),
            constraints=[
                constraints.AllowedValues(['direct', 'reverse'])
            ],
            required=True,
            update_allowed=True
        ),
        USE_REQUEST_BODY_AS_INPUT: properties.Schema(
            properties.Schema.BOOLEAN,
            _('Defines the method in which the request body for signaling a '
              'workflow would be parsed. In case this property is set to '
              'True, the body would be parsed as a simple json where each '
              'key is a workflow input, in other cases body would be parsed '
              'expecting a specific json format with two keys: "input" and '
              '"params"'),
            update_allowed=True,
            support_status=support.SupportStatus(version='6.0.0')
        ),
        DESCRIPTION: properties.Schema(
            properties.Schema.STRING,
            _('Workflow description.'),
            update_allowed=True
        ),
        INPUT: properties.Schema(
            properties.Schema.MAP,
            _('Dictionary which contains input for workflow.'),
            update_allowed=True
        ),
        OUTPUT: properties.Schema(
            properties.Schema.MAP,
            _('Any data structure arbitrarily containing YAQL '
              'expressions that defines workflow output. May be '
              'nested.'),
            update_allowed=True
        ),
        PARAMS: properties.Schema(
            properties.Schema.MAP,
            _("Workflow additional parameters. If Workflow is reverse typed, "
              "params requires 'task_name', which defines initial task."),
            update_allowed=True
        ),
        TASK_DEFAULTS: properties.Schema(
            properties.Schema.MAP,
            _("Default settings for some of task "
              "attributes defined "
              "at workflow level."),
            schema={
                ON_SUCCESS: properties.Schema(
                    properties.Schema.LIST,
                    _('List of tasks which will run after '
                      'the task has completed successfully.')
                ),
                ON_ERROR: properties.Schema(
                    properties.Schema.LIST,
                    _('List of tasks which will run after '
                      'the task has completed with an error.')
                ),
                ON_COMPLETE: properties.Schema(
                    properties.Schema.LIST,
                    _('List of tasks which will run after '
                      'the task has completed regardless of whether '
                      'it is successful or not.')
                ),
                REQUIRES: properties.Schema(
                    properties.Schema.LIST,
                    _('List of tasks which should be executed before '
                      'this task. Used only in reverse workflows.')
                ),
                RETRY: properties.Schema(
                    properties.Schema.MAP,
                    _('Defines a pattern how task should be repeated in '
                      'case of an error.')
                ),
                WAIT_BEFORE: properties.Schema(
                    properties.Schema.INTEGER,
                    _('Defines a delay in seconds that Mistral Engine'
                      ' should wait before starting a task.')
                ),
                WAIT_AFTER: properties.Schema(
                    properties.Schema.INTEGER,
                    _('Defines a delay in seconds that Mistral Engine'
                      ' should wait after a task has completed before'
                      ' starting next tasks defined in '
                      'on-success, on-error or on-complete.')
                ),
                PAUSE_BEFORE: properties.Schema(
                    properties.Schema.BOOLEAN,
                    _('Defines whether Mistral Engine should put the '
                      'workflow on hold or not before starting a task')
                ),
                TIMEOUT: properties.Schema(
                    properties.Schema.INTEGER,
                    _('Defines a period of time in seconds after which '
                      'a task will be failed automatically '
                      'by engine if hasn\'t completed.')
                ),
            },
            update_allowed=True
        ),
        TASKS: properties.Schema(
            properties.Schema.LIST,
            _('Dictionary containing workflow tasks.'),
            schema=properties.Schema(
                properties.Schema.MAP,
                schema={
                    TASK_NAME: properties.Schema(
                        properties.Schema.STRING,
                        _('Task name.'),
                        required=True
                    ),
                    TASK_DESCRIPTION: properties.Schema(
                        properties.Schema.STRING,
                        _('Task description.')
                    ),
                    TASK_INPUT: properties.Schema(
                        properties.Schema.MAP,
                        _('Actual input parameter values of the task.')
                    ),
                    ACTION: properties.Schema(
                        properties.Schema.STRING,
                        _('Name of the action associated with the task. '
                          'Either action or workflow may be defined in the '
                          'task.')
                    ),
                    WORKFLOW: properties.Schema(
                        properties.Schema.STRING,
                        _('Name of the workflow associated with the task. '
                          'Can be defined by intrinsic function get_resource '
                          'or by name of the referenced workflow, i.e. '
                          '{ workflow: wf_name } or '
                          '{ workflow: { get_resource: wf_name }}. Either '
                          'action or workflow may be defined in the task.')
                    ),
                    PUBLISH: properties.Schema(
                        properties.Schema.MAP,
                        _('Dictionary of variables to publish to '
                          'the workflow context.')
                    ),
                    ON_SUCCESS: properties.Schema(
                        properties.Schema.LIST,
                        _('List of tasks which will run after '
                          'the task has completed successfully.')
                    ),
                    ON_ERROR: properties.Schema(
                        properties.Schema.LIST,
                        _('List of tasks which will run after '
                          'the task has completed with an error.')
                    ),
                    ON_COMPLETE: properties.Schema(
                        properties.Schema.LIST,
                        _('List of tasks which will run after '
                          'the task has completed regardless of whether '
                          'it is successful or not.')
                    ),
                    REQUIRES: properties.Schema(
                        properties.Schema.LIST,
                        _('List of tasks which should be executed before '
                          'this task. Used only in reverse workflows.')
                    ),
                    RETRY: properties.Schema(
                        properties.Schema.MAP,
                        _('Defines a pattern how task should be repeated in '
                          'case of an error.')
                    ),
                    WAIT_BEFORE: properties.Schema(
                        properties.Schema.INTEGER,
                        _('Defines a delay in seconds that Mistral Engine '
                          'should wait before starting a task.')
                    ),
                    WAIT_AFTER: properties.Schema(
                        properties.Schema.INTEGER,
                        _('Defines a delay in seconds that Mistral '
                          'Engine should wait after '
                          'a task has completed before starting next tasks '
                          'defined in on-success, on-error or on-complete.')
                    ),
                    PAUSE_BEFORE: properties.Schema(
                        properties.Schema.BOOLEAN,
                        _('Defines whether Mistral Engine should '
                          'put the workflow on hold '
                          'or not before starting a task.')
                    ),
                    TIMEOUT: properties.Schema(
                        properties.Schema.INTEGER,
                        _('Defines a period of time in seconds after which a '
                          'task will be failed automatically by engine '
                          'if hasn\'t completed.')
                    ),
                    WITH_ITEMS: properties.Schema(
                        properties.Schema.STRING,
                        _('If configured, it allows to run action or workflow '
                          'associated with a task multiple times '
                          'on a provided list of items.')
                    ),
                    KEEP_RESULT: properties.Schema(
                        properties.Schema.BOOLEAN,
                        _('Allowing to not store action results '
                          'after task completion.')
                    ),
                    TARGET: properties.Schema(
                        properties.Schema.STRING,
                        _('It defines an executor to which task action '
                          'should be sent to.')
                    ),
                    JOIN: properties.Schema(
                        properties.Schema.STRING,
                        _('Allows to synchronize multiple parallel workflow branches and aggregate their data.')
                    ),
                },
            ),
            required=True,
            update_allowed=True
        )
    }

    attributes_schema = {
        WORKFLOW_DATA: attributes.Schema(
            _('A dictionary which contains name and input of the workflow.')
        ),
        ALARM_URL: attributes.Schema(
            _("A signed url to create executions for workflows specified in "
              "Workflow resource.")
        ),
        EXECUTIONS: attributes.Schema(
            _("List of workflows' executions, each of them is a dictionary "
              "with information about execution. Each dictionary returns "
              "values for next keys: id, workflow_name, created_at, "
              "updated_at, state for current execution state, input, output.")
        )
    }

    def FnGetRefId(self):
        return self._workflow_name()

    def _get_inputs_and_params(self, data):
        inputs = None
        params = None
        if self.properties.get(self.USE_REQUEST_BODY_AS_INPUT):
            inputs = data
        else:
            if data is not None:
                inputs = data.get(self.SIGNAL_DATA_INPUT)
                params = data.get(self.SIGNAL_DATA_PARAMS)
        return inputs, params

    def _validate_signal_data(self, data):
        input_value, params_value = self._get_inputs_and_params(data)
        if input_value is not None:
            if not isinstance(input_value, dict):
                message = (_('Input in signal data must be a map, '
                             'find a %s') % type(input_value))
                raise exception.StackValidationFailed(
                    error=_('Signal data error'),
                    message=message)
            for key in six.iterkeys(input_value):
                if (self.properties.get(self.INPUT) is None
                    or key not in self.properties.get(self.INPUT)):
                    message = _('Unknown input %s') % key
                    raise exception.StackValidationFailed(
                        error=_('Signal data error'),
                        message=message)
        if params_value is not None and not isinstance(params_value, dict):
            message = (_('Params must be a map, find a '
                         '%s') % type(params_value))
            raise exception.StackValidationFailed(
                error=_('Signal data error'),
                message=message)

    def validate(self):
        super(Workflow, self).validate()
        if self.properties.get(self.TYPE) == 'reverse':
            params = self.properties.get(self.PARAMS)
            if params is None or not params.get('task_name'):
                raise exception.StackValidationFailed(
                    error=_('Mistral resource validation error'),
                    path=[self.name,
                          ('properties'
                           if self.stack.t.VERSION == 'heat_template_version'
                           else 'Properties'),
                          self.PARAMS],
                    message=_("'task_name' is not assigned in 'params' "
                              "in case of reverse type workflow.")
                )
        for task in self.properties.get(self.TASKS):
            wf_value = task.get(self.WORKFLOW)
            action_value = task.get(self.ACTION)
            if wf_value and action_value:
                raise exception.ResourcePropertyConflict(self.WORKFLOW,
                                                         self.ACTION)
            if not wf_value and not action_value:
                raise exception.PropertyUnspecifiedError(self.WORKFLOW,
                                                         self.ACTION)
            if (task.get(self.REQUIRES) is not None
                    and self.properties.get(self.TYPE)) == 'direct':
                msg = _("task %(task)s contains property 'requires' "
                        "in case of direct workflow. Only reverse workflows "
                        "can contain property 'requires'.") % {
                    'name': self.name,
                    'task': task.get(self.TASK_NAME)
                }
                raise exception.StackValidationFailed(
                    error=_('Mistral resource validation error'),
                    path=[self.name,
                          ('properties'
                           if self.stack.t.VERSION == 'heat_template_version'
                           else 'Properties'),
                          self.TASKS,
                          task.get(self.TASK_NAME),
                          self.REQUIRES],
                    message=msg)

    def _workflow_name(self):
        return self.properties.get(self.NAME) or self.physical_resource_name()

    def build_tasks(self, props):
        for task in props[self.TASKS]:
            current_task = {}
            wf_value = task.get(self.WORKFLOW)
            if wf_value is not None:
                if wf_value in [res.resource_id
                                for res in six.itervalues(self.stack)]:
                    current_task.update({self.WORKFLOW: wf_value})
                else:
                    msg = _("No such workflow %s") % wf_value
                    raise ValueError(msg)

            task_keys = [key for key in self._TASKS_KEYS
                         if key not in [self.WORKFLOW, self.TASK_NAME]]
            for task_prop in task_keys:
                if task.get(task_prop) is not None:
                    current_task.update(
                        {task_prop.replace('_', '-'): task[task_prop]})

            yield {task[self.TASK_NAME]: current_task}

    def prepare_properties(self, props):
        """Prepare correct YAML-formatted definition for Mistral."""
        defn_name = self._workflow_name()
        definition = {'version': '2.0',
                      defn_name: {self.TYPE: props.get(self.TYPE),
                                  self.DESCRIPTION: props.get(
                                      self.DESCRIPTION),
                                  self.OUTPUT: props.get(self.OUTPUT)}}
        for key in list(definition[defn_name].keys()):
            if definition[defn_name][key] is None:
                del definition[defn_name][key]
        if props.get(self.INPUT) is not None:
            definition[defn_name][self.INPUT] = list(props.get(
                self.INPUT).keys())
        definition[defn_name][self.TASKS] = {}
        for task in self.build_tasks(props):
            definition.get(defn_name).get(self.TASKS).update(task)

        if props.get(self.TASK_DEFAULTS) is not None:
            definition[defn_name][self.TASK_DEFAULTS.replace('_', '-')] = {
                k.replace('_', '-'): v for k, v in
                six.iteritems(props.get(self.TASK_DEFAULTS)) if v}

        return yaml.dump(definition, Dumper=yaml.CSafeDumper
                         if hasattr(yaml, 'CSafeDumper')
                         else yaml.SafeDumper)

    def handle_create(self):
        super(Workflow, self).handle_create()
        props = self.prepare_properties(self.properties)
        try:
            workflow = self.client().workflows.create(props)
        except Exception as ex:
            raise exception.ResourceFailure(ex, self)
        # NOTE(prazumovsky): Mistral uses unique names for resource
        # identification.
        self.resource_id_set(workflow[0].name)

    def handle_signal(self, details=None):
        self._validate_signal_data(details)

        result_input = {}
        result_params = {}
        inputs, params = self._get_inputs_and_params(details)
        if inputs is not None:
            # NOTE(prazumovsky): Signal can contains some data, interesting
            # for workflow, e.g. inputs. So, if signal data contains input
            # we update override inputs, other leaved defined in template.
            for key, value in six.iteritems(
                    self.properties.get(self.INPUT)):
                result_input.update(
                    {key: inputs.get(key) or value})
        if params is not None:
            if self.properties.get(self.PARAMS) is not None:
                result_params.update(self.properties.get(self.PARAMS))
            result_params.update(params)

        if not result_input and self.properties.get(self.INPUT):
            result_input.update(self.properties.get(self.INPUT))
        if not result_params and self.properties.get(self.PARAMS):
            result_params.update(self.properties.get(self.PARAMS))

        try:
            execution = self.client().executions.create(
                self._workflow_name(),
                jsonutils.dumps(result_input),
                **result_params)
        except Exception as ex:
            raise exception.ResourceFailure(ex, self)
        executions = [execution.id]
        if self.EXECUTIONS in self.data():
            executions.extend(self.data().get(self.EXECUTIONS).split(','))
        self.data_set(self.EXECUTIONS, ','.join(executions))

    def handle_update(self, json_snippet, tmpl_diff, prop_diff):
        update_allowed = [self.INPUT, self.PARAMS, self.DESCRIPTION]
        for prop in update_allowed:
            if prop in prop_diff:
                del prop_diff[prop]
        if len(prop_diff) > 0:
            new_props = self.prepare_properties(tmpl_diff['Properties'])
            try:
                workflow = self.client().workflows.update(new_props)
            except Exception as ex:
                raise exception.ResourceFailure(ex, self)
            self.data_set(self.NAME, workflow[0].name)
            self.resource_id_set(workflow[0].name)

    def handle_delete(self):
        super(Workflow, self).handle_delete()

        if self.resource_id is None:
            return

        try:
            self.client().workflows.delete(self.resource_id)
            if self.data().get(self.EXECUTIONS):
                for id in self.data().get(self.EXECUTIONS).split(','):
                    self.client().executions.delete(id)
        except Exception as e:
            self.client_plugin().ignore_not_found(e)

    def _resolve_attribute(self, name):
        if name == self.EXECUTIONS:
            if self.EXECUTIONS not in self.data():
                return []

            def parse_execution_response(execution):
                return {
                    'id': execution.id,
                    'workflow_name': execution.workflow_name,
                    'created_at': execution.created_at,
                    'updated_at': execution.updated_at,
                    'state': execution.state,
                    'input': jsonutils.loads(six.text_type(execution.input)),
                    'output': jsonutils.loads(six.text_type(execution.output))
                }

            return [parse_execution_response(
                self.client().executions.get(exec_id))
                for exec_id in
                self.data().get(self.EXECUTIONS).split(',')]

        elif name == self.WORKFLOW_DATA:
            return {self.NAME: self.resource_id,
                    self.INPUT: self.properties.get(self.INPUT)}

        elif name == self.ALARM_URL:
            return six.text_type(self._get_signed_url())

    # TODO(tlashchova): remove this method when mistralclient>1.0.0 is used.
    def _show_resource(self):
        workflow = self.client().workflows.get(self.resource_id)
        if hasattr(workflow, 'to_dict'):
            super(Workflow, self)._show_resource()
        return workflow._data


def resource_mapping():
    return {
        'OS::Mistral::Workflow': Workflow
    }