# Copyright (c) 2022, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
from tests.common.test_utils import construct_perf_analyzer_config

from model_analyzer.perf_analyzer.perf_config import PerfAnalyzerConfig
from model_analyzer.config.generate.perf_analyzer_config_generator import PerfAnalyzerConfigGenerator
from model_analyzer.config.input.config_command_profile \
     import ConfigCommandProfile
from model_analyzer.cli.cli import CLI
from .common import test_result_collector as trc
from .common.test_utils import convert_to_bytes, construct_run_config_measurement
from .mocks.mock_config import MockConfig
from .mocks.mock_os import MockOSMethods
from model_analyzer.config.generate.generator_utils import GeneratorUtils as utils
from unittest.mock import MagicMock
from unittest.mock import patch

from model_analyzer.config.input.config_defaults import \
    DEFAULT_BATCH_SIZES, DEFAULT_TRITON_LAUNCH_MODE, \
    DEFAULT_CLIENT_PROTOCOL, DEFAULT_TRITON_INSTALL_PATH, DEFAULT_OUTPUT_MODEL_REPOSITORY, \
    DEFAULT_TRITON_INSTALL_PATH, DEFAULT_OUTPUT_MODEL_REPOSITORY, \
    DEFAULT_TRITON_HTTP_ENDPOINT, DEFAULT_TRITON_GRPC_ENDPOINT, DEFAULT_MEASUREMENT_MODE, \
    DEFAULT_RUN_CONFIG_MAX_CONCURRENCY, DEFAULT_REQUEST_COUNT_MULTIPLIER


class TestPerfAnalyzerConfigGenerator(trc.TestResultCollector):

    def __init__(self, methodname):
        super().__init__(methodname)
        self._perf_throughput = 1

    def test_set_last_results(self):
        """
        Test set_last_results() with multi model
        
        Confirm that set_last_results will properly choose the measurement with
        the highest total throughput 
        """
        measurement1 = self.make_multi_model_measurement(
            ["modelA", "modelB"], [{
                "perf_throughput": 1
            }, {
                "perf_throughput": 2
            }])

        measurement2 = self.make_multi_model_measurement(
            ["modelA", "modelB"], [{
                "perf_throughput": 7
            }, {
                "perf_throughput": 7
            }])

        measurement3 = self.make_multi_model_measurement(
            ["modelA", "modelB"], [{
                "perf_throughput": 10
            }, {
                "perf_throughput": 2
            }])

        pacg = PerfAnalyzerConfigGenerator(MagicMock(),
                                           MagicMock(),
                                           MagicMock(),
                                           MagicMock(),
                                           early_exit_enable=False)

        pacg.set_last_results([measurement1, measurement2, measurement3])
        self.assertEqual(pacg._last_results[0], measurement2)

    def test_default(self):
        """
        Test Default:  
            - No CLI options specified
        
        Default (1) value will be used for batch size
        and log2(DEFAULT_RUN_CONFIG_MAX_CONCURRENCY)+1 configs 
        will be generated by the auto-search
        """

        # yapf: disable
        yaml_content = convert_to_bytes("""
            profile_models:
                - my-model
            """)
        # yapf: enable

        concurrencies = utils.generate_doubled_list(
            1, DEFAULT_RUN_CONFIG_MAX_CONCURRENCY)
        expected_configs = [
            construct_perf_analyzer_config(concurrency=c) for c in concurrencies
        ]

        self._run_and_test_perf_analyzer_config_generator(
            yaml_content, expected_configs)

    def test_search_disabled(self):
        """ 
        Test Search Disabled: 
            - Run Config Search disabled
        
        Default (1) value will be used for batch size
        and concurrency will be set to 1
        """

        # yapf: disable
        yaml_content = convert_to_bytes("""
            profile_models:
                - my-model
            """)
        # yapf: enable

        expected_configs = [construct_perf_analyzer_config()]

        self._run_and_test_perf_analyzer_config_generator(
            yaml_content, expected_configs, '--run-config-search-disable')

    def test_c_api(self):
        """ 
        Test C_API: 
            - Launch mode is C_API
        
        Default (1) values will be used for batch size/concurrency 
        and only one config will be generated 
        """

        # yapf: disable
        yaml_content = convert_to_bytes("""
            profile_models:
                - my-model
            """)
        # yapf: enable

        concurrencies = utils.generate_doubled_list(
            1, DEFAULT_RUN_CONFIG_MAX_CONCURRENCY)
        expected_configs = [
            construct_perf_analyzer_config(concurrency=c, launch_mode='c_api')
            for c in concurrencies
        ]

        self._run_and_test_perf_analyzer_config_generator(
            yaml_content, expected_configs, '--triton-launch-mode=c_api')

    def test_http(self):
        """ 
        Test HTTP: 
            - Client protocol is HTTP
        
        Default (1) values will be used for batch size/concurrency 
        and only one config will be generated 
        """

        # yapf: disable
        yaml_content = convert_to_bytes("""
            profile_models:
                - my-model
            """)
        # yapf: enable

        concurrencies = utils.generate_doubled_list(
            1, DEFAULT_RUN_CONFIG_MAX_CONCURRENCY)
        expected_configs = [
            construct_perf_analyzer_config(concurrency=c,
                                           client_protocol='http')
            for c in concurrencies
        ]

        self._run_and_test_perf_analyzer_config_generator(
            yaml_content, expected_configs, '--client-protocol=http')

    def test_batch_size_search_disabled(self):
        """ 
        Test Batch Size Search Disabled: 
            - Schmoo batch sizes
            - Run Config Search disabled
        
        Batch sizes: 1,2,4
        Default (1) value will be used concurrency 
        and 3 configs will be generated 
        """

        # yapf: disable
        yaml_content = convert_to_bytes("""
            profile_models:
                - my-model
            """)
        # yapf: enable

        batch_sizes = [1, 2, 4]
        expected_configs = [
            construct_perf_analyzer_config(batch_size=b) for b in batch_sizes
        ]

        pa_cli_args = ['-b 1,2,4', '--run-config-search-disable']
        self._run_and_test_perf_analyzer_config_generator(
            yaml_content, expected_configs, pa_cli_args)

    def test_batch_size_search_enabled(self):
        """ 
        Test Batch Size Search Enabled: 
            - Schmoo batch sizes
            - Run Config Search enabled
        
        Batch sizes: 1,2,4
        Concurrency: log2(DEFAULT_RUN_CONFIG_MAX_CONCURRENCY)+1
        """

        # yapf: disable
        yaml_content = convert_to_bytes("""
            profile_models:
                - my-model
            """)
        # yapf: enable

        batch_sizes = [1, 2, 4]
        concurrencies = utils.generate_doubled_list(
            1, DEFAULT_RUN_CONFIG_MAX_CONCURRENCY)
        expected_configs = [
            construct_perf_analyzer_config(batch_size=b, concurrency=c)
            for b in batch_sizes
            for c in concurrencies
        ]

        pa_cli_args = ['-b 1,2,4']
        self._run_and_test_perf_analyzer_config_generator(
            yaml_content, expected_configs, pa_cli_args)

    def test_concurrency(self):
        """ 
        Test Concurrency: 
            - Schmoo concurrency
            - Test with auto-search enabled & disabled
        
        Concurrency: 1-4
        Default (1) value will be used for batch size 
        and 4 configs will be generated 
        """

        # yapf: disable
        yaml_content = convert_to_bytes("""
            profile_models:
                - my-model
            """)
        # yapf: enable

        concurrencies = [1, 2, 3, 4]
        expected_configs = [
            construct_perf_analyzer_config(concurrency=c) for c in concurrencies
        ]

        pa_cli_args = ['-c 1,2,3,4']
        self._run_and_test_perf_analyzer_config_generator(
            yaml_content, expected_configs, pa_cli_args)

        pa_cli_args = ['-c 1,2,3,4', '--run-config-search-disable']
        self._run_and_test_perf_analyzer_config_generator(
            yaml_content, expected_configs, pa_cli_args)

    def test_batch_size_and_concurrency(self):
        """
        Test Batch Size and Concurrency:
            - Schmoo batch sizes and concurrency
            - Run Config Search enabled & disabled

        Batch sizes: 1,2,4
        Concurrency: 1-4
        

        12 configs will be generated
        """

        # yapf: disable
        yaml_content = convert_to_bytes("""
            profile_models:
                - my-model
            """)
        # yapf: enable

        batch_sizes = [1, 2, 4]
        concurrencies = [1, 2, 3, 4]

        expected_configs = [
            construct_perf_analyzer_config(batch_size=b, concurrency=c)
            for b in batch_sizes
            for c in concurrencies
        ]

        pa_cli_args = ['-b 1,2,4', '-c 1,2,3,4']
        self._run_and_test_perf_analyzer_config_generator(
            yaml_content, expected_configs, pa_cli_args)

        pa_cli_args = ['-b 1,2,4', '-c 1,2,3,4', '--run-config-search-disable']
        self._run_and_test_perf_analyzer_config_generator(
            yaml_content, expected_configs, pa_cli_args)

    def test_max_concurrency(self):
        """ 
        Test Max Concurrency: 
            - Change max concurrency to non-default value
        
        Max Concurrency: 16
        Default (1) value will be used for batch size 
        and 5 configs (log2(16)+1) will be generated 
        """

        # yapf: disable
        yaml_content = convert_to_bytes("""
            profile_models:
                - my-model
            """)
        # yapf: enable

        concurrencies = utils.generate_doubled_list(1, 16)
        expected_configs = [
            construct_perf_analyzer_config(concurrency=c) for c in concurrencies
        ]

        pa_cli_args = ['--run-config-search-max-concurrency', '16']
        self._run_and_test_perf_analyzer_config_generator(
            yaml_content, expected_configs, pa_cli_args)

    def test_min_concurrency(self):
        """ 
        Test Min Concurrency: 
            - Change min concurrency to non-default value
        
        Min Concurrency: 5
        2 configs [5, 10] will be generated 
        """

        # yapf: disable
        yaml_content = convert_to_bytes("""
            profile_models:
                - my-model
            """)
        # yapf: enable

        concurrencies = [5, 10]
        expected_configs = [
            construct_perf_analyzer_config(concurrency=c) for c in concurrencies
        ]

        pa_cli_args = [
            '--run-config-search-min-concurrency', '5',
            '--run-config-search-max-concurrency', '16'
        ]
        self._run_and_test_perf_analyzer_config_generator(
            yaml_content, expected_configs, pa_cli_args)

    def test_perf_analyzer_flags(self):
        """
        Test Perf Analyzer Flags:  
            - No CLI options specified
            - Percentile (PA flag) set in model's YAML
        
        Default (1) value will be used for batch size
        and log2(DEFAULT_RUN_CONFIG_MAX_CONCURRENCY)+1 configs 
        will be generated by the auto-search
        """

        # yapf: disable
        yaml_content = convert_to_bytes("""
            profile_models:
                - my-model:
                    perf_analyzer_flags:
                        percentile: 96
            """)
        # yapf: enable

        concurrencies = utils.generate_doubled_list(
            1, DEFAULT_RUN_CONFIG_MAX_CONCURRENCY)
        expected_configs = [
            construct_perf_analyzer_config(
                concurrency=c, perf_analyzer_flags={'percentile': '96'})
            for c in concurrencies
        ]

        self._run_and_test_perf_analyzer_config_generator(
            yaml_content, expected_configs)

    def test_perf_analyzer_config_ssl_options(self):
        """
        Test Perf Analyzer SSL options:  
            - No CLI options specified
        """

        # yapf: disable
        yaml_content = convert_to_bytes("""
            profile_models:
                - my-model:
                    perf_analyzer_flags:
                        ssl-grpc-root-certifications-file: a
                        ssl-grpc-private-key-file: b
                        ssl-grpc-certificate-chain-file: c
                        ssl-https-verify-peer: 1
                        ssl-https-verify-host: 2
                        ssl-https-ca-certificates-file: d
                        ssl-https-client-certificate-type: e
                        ssl-https-client-certificate-file: f
                        ssl-https-private-key-type: g
                        ssl-https-private-key-file: h
            """)
        # yapf: enable

        concurrencies = utils.generate_doubled_list(
            1, DEFAULT_RUN_CONFIG_MAX_CONCURRENCY)
        expected_configs = [
            construct_perf_analyzer_config(
                concurrency=c,
                perf_analyzer_flags={
                    'ssl-grpc-root-certifications-file': 'a',
                    'ssl-grpc-private-key-file': 'b',
                    'ssl-grpc-certificate-chain-file': 'c',
                    'ssl-https-verify-peer': '1',
                    'ssl-https-verify-host': '2',
                    'ssl-https-ca-certificates-file': 'd',
                    'ssl-https-client-certificate-type': 'e',
                    'ssl-https-client-certificate-file': 'f',
                    'ssl-https-private-key-type': 'g',
                    'ssl-https-private-key-file': 'h',
                }) for c in concurrencies
        ]

        self._run_and_test_perf_analyzer_config_generator(
            yaml_content, expected_configs)

    def test_early_exit_on_no_plateau(self):
        """ 
        Test if early_exit is true but the throughput is still increasing, we 
        do not early exit
        """
        # yapf: disable
        yaml_content = convert_to_bytes("""
            profile_models:
                - my-model
            """)
        # yapf: enable

        concurrencies = utils.generate_doubled_list(1, 64)
        expected_configs = [
            construct_perf_analyzer_config(concurrency=c) for c in concurrencies
        ]

        pa_cli_args = ['--run-config-search-max-concurrency', '64']
        self._run_and_test_perf_analyzer_config_generator(yaml_content,
                                                          expected_configs,
                                                          pa_cli_args,
                                                          early_exit=True)

    def test_early_exit_on_yes_plateau(self):
        """ 
        Test if early_exit is true and the throughput plateaus, we do early exit
        """

        # yapf: disable
        yaml_content = convert_to_bytes("""
            profile_models:
                - my-model
            """)
        # yapf: enable

        concurrencies = utils.generate_doubled_list(1, 32)
        expected_configs = [
            construct_perf_analyzer_config(concurrency=c) for c in concurrencies
        ]

        pa_cli_args = ['--run-config-search-max-concurrency', '64']
        with patch.object(TestPerfAnalyzerConfigGenerator,
                          "_get_next_perf_throughput_value") as mock_method:
            mock_method.side_effect = [1, 2, 4, 4, 4, 4, 4]
            self._run_and_test_perf_analyzer_config_generator(yaml_content,
                                                              expected_configs,
                                                              pa_cli_args,
                                                              early_exit=True)

    def test_early_exit_off_yes_plateau(self):
        """ 
        Test if early_exit is off and the throughput plateaus, we do not early exit
        """

        # yapf: disable
        yaml_content = convert_to_bytes("""
            profile_models:
                - my-model
            """)
        # yapf: enable

        concurrencies = utils.generate_doubled_list(1, 64)
        expected_configs = [
            construct_perf_analyzer_config(concurrency=c) for c in concurrencies
        ]

        pa_cli_args = ['--run-config-search-max-concurrency', '64']
        with patch.object(TestPerfAnalyzerConfigGenerator,
                          "_get_next_perf_throughput_value") as mock_method:
            mock_method.side_effect = [1, 2, 4, 4, 4, 4, 4]
            self._run_and_test_perf_analyzer_config_generator(yaml_content,
                                                              expected_configs,
                                                              pa_cli_args,
                                                              early_exit=False)

    def test_calculate_measurement_request_count(self):
        """
        Test that this method returns the correct request count value
        """
        pacg = PerfAnalyzerConfigGenerator(MagicMock(), MagicMock(),
                                           MagicMock(), MagicMock(),
                                           MagicMock(), 128)

        self.assertEqual(DEFAULT_REQUEST_COUNT_MULTIPLIER * 256,
                         pacg._calculate_measurement_request_count(128))

    def _get_next_measurement(self):

        throughput_value = self._get_next_perf_throughput_value()
        if throughput_value is None:
            return None
        else:
            return construct_run_config_measurement(
                model_name=MagicMock(),
                model_config_names=["test_model_config_name"],
                model_specific_pa_params=MagicMock(),
                gpu_metric_values=MagicMock(),
                non_gpu_metric_values=[{
                    "perf_throughput": throughput_value
                }])

    def _get_next_perf_throughput_value(self):
        self._perf_throughput *= 2
        return self._perf_throughput

    def _run_and_test_perf_analyzer_config_generator(self,
                                                     yaml_content,
                                                     expected_configs,
                                                     pa_cli_args=None,
                                                     early_exit=False):
        args = [
            'model-analyzer', 'profile', '--model-repository', 'cli_repository',
            '-f', 'path-to-config-file'
        ]

        if type(pa_cli_args) == list:
            args = args + pa_cli_args
        elif type(pa_cli_args) == str:
            args.append(pa_cli_args)

        config = self._evaluate_config(args, yaml_content)

        pacg = PerfAnalyzerConfigGenerator(
            config, config.profile_models[0].model_name(),
            config.profile_models[0].perf_analyzer_flags(),
            config.profile_models[0].parameters(), early_exit)

        perf_analyzer_configs = []
        pacg_generator = pacg.next_config()
        while not pacg.is_done():
            perf_analyzer_configs.append(next(pacg_generator))
            pacg.set_last_results([self._get_next_measurement()])

        self.assertEqual(len(expected_configs), len(perf_analyzer_configs))
        for i in range(len(expected_configs)):
            self.assertEqual(expected_configs[i]._options['-m'],
                             perf_analyzer_configs[i]._options['-m'])
            self.assertEqual(expected_configs[i]._options['-b'],
                             perf_analyzer_configs[i]._options['-b'])
            self.assertEqual(expected_configs[i]._options['-i'],
                             perf_analyzer_configs[i]._options['-i'])
            self.assertEqual(expected_configs[i]._options['-u'],
                             perf_analyzer_configs[i]._options['-u'])

            self.assertEqual(
                expected_configs[i]._args['concurrency-range'],
                perf_analyzer_configs[i]._args['concurrency-range'])
            self.assertEqual(expected_configs[i]._args['measurement-mode'],
                             perf_analyzer_configs[i]._args['measurement-mode'])
            self.assertEqual(expected_configs[i]._args['service-kind'],
                             perf_analyzer_configs[i]._args['service-kind'])
            self.assertEqual(
                expected_configs[i]._args['triton-server-directory'],
                perf_analyzer_configs[i]._args['triton-server-directory'])
            self.assertEqual(expected_configs[i]._args['model-repository'],
                             perf_analyzer_configs[i]._args['model-repository'])

            # Future-proofing (in case a new field gets added)
            self.assertEqual(expected_configs[i]._options,
                             perf_analyzer_configs[i]._options)
            self.assertEqual(expected_configs[i]._args,
                             perf_analyzer_configs[i]._args)
            self.assertEqual(expected_configs[i]._additive_args,
                             perf_analyzer_configs[i]._additive_args)

    def _evaluate_config(self, args, yaml_content):
        mock_config = MockConfig(args, yaml_content)
        mock_config.start()
        config = ConfigCommandProfile()
        cli = CLI()
        cli.add_subcommand(
            cmd='profile',
            help=
            'Run model inference profiling based on specified CLI or config options.',
            config=config)
        cli.parse()
        mock_config.stop()
        return config

    def setUp(self):
        # Mock path validation
        self.mock_os = MockOSMethods(
            mock_paths=['model_analyzer.config.input.config_utils'])
        self.mock_os.start()

    def tearDown(self):
        self.mock_os.stop()
        patch.stopall()

    def make_multi_model_measurement(self, model_names, non_gpu_metric_values):
        return construct_run_config_measurement(
            model_name=MagicMock(),
            model_config_names=model_names,
            model_specific_pa_params=MagicMock(),
            gpu_metric_values=MagicMock(),
            non_gpu_metric_values=non_gpu_metric_values)


if __name__ == '__main__':
    unittest.main()
