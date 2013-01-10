import abc
import copy
import logging 
import os
import uuid
import sys
from yapsy.PluginManager import PluginManager

# A-Rast modules
import assembly

class BasePlugin(object):
    """ 
    job_data dictionary must contain:
    - job_id
    - uid

    job_data could contain (dependent on stage of pipeline or input data)
    - reads: list of tuples eg. [('/data/unpaired.fa,), ('/data/1a.fa', '/data/1b.fa')]
    - contigs: list of contig files

    Available instance attributes:
    - self.outpath
    - self.PARAM_IN_CONFIG_FILE
        eg. self.k = 29
    """
        
    

    def create_directories(self, job_data):
        datapath = (job_data['datapath'] + '/' + str(job_data['job_id']) + 
                    '/' + self.name + '_' + str(uuid.uuid4())) + '/'
        logging.info("Creating directory: {}".format(datapath))

        os.makedirs(datapath)
        return datapath

    def get_valid_reads(self, job_data):
        """
        Based on plugin config file, filters for valid filetypes
        """

        filetypes = self.filetypes.split(',')
        filetypes = ['.' + filetype for filetype in filetypes]
        valid_files = []
        for filetype in filetypes:
            for d in job_data['reads']:
                if d['files'][0].endswith(filetype):
                    valid_files.append(d)
        if not valid_files:
            raise Exception('No valid input files (Compression unsupported)')
        return valid_files

    def init_settings(self, settings, job_data):
        self.threads = 1
        self.out_report = job_data['out_report'] #Job log file
        self.out_module = open(os.path.join(self.outpath, '{}.out'.format(self.name)), 'w')
        print type(self.out_module)
        for kv in settings:
            setattr(self, kv[0], kv[1])

        for kv in job_data['params']:
            print "Override: {}".format(kv)
            setattr(self, kv[0], kv[1])

    def linuxRam(self):
        """Returns the RAM of a linux system"""
        totalMemory = os.popen("free -m").readlines()[1].split()[1]
        return int(totalMemory)

    def get_all_output_files(self):
        """ Returns list of all files created after run. """
        if os.path.exists(self.outpath):
            return [os.path.join(self.outpath, f) for 
                    f in os.listdir(self.outpath)]
        raise Exception("No output files in directory")

    def run_checks(self, settings, job_data):
        logging.info("Doing checks")
        #Check binary exists
        #Check data is valid
        pass

    def setname(self, name):
        self.name = name

    def tar(self, files, job_id):
        return assembly.tar_list(self.outpath, files, 
                                 self.name + str(job_id) + '.tar.gz')

    def tar_output(self, job_id):
        files = [self.outpath + file for file in os.listdir(self.outpath)]
        return assembly.tar_list(self.outpath, files, 
                                 self.name + str(job_id) + '.tar.gz')


    def update_settings(self, job_data):
        """
        Overwrite any new settings passed in JOB_DATA
        """
        pass

    def update_status(self):
        pass

    def write_report(self):
        pass

    
class BaseAssembler(BasePlugin):
    """
    An assembler plugin should implement a run() function

    """
    # Default behavior for run()
    INPUT = 'reads'
    OUTPUT = 'contigs'

    def __call__(self, settings, job_data):
        self.run_checks(settings, job_data)
        logging.info("{} Settings: {}".format(self.name, settings))
        self.outpath = self.create_directories(job_data)
        self.init_settings(settings, job_data)
        valid_files = self.get_valid_reads(job_data)
        output = self.run(valid_files)
        self.out_module.close()
        return output


    def get_files(self, file_dicts):
        """ Return a list of files from dicts. """
        files = []
        for d in file_dicts:
            files += d['files']
        return files


    # Must implement run() method
    @abc.abstractmethod
    def run(self, reads):
        """
        Input: list of dicts contain file and read info
        Output: list of full paths to contig files.  File extensions should reflect
          the file type
          eg. return ['/data/contigs1.fa', '/data/contigs2.fa']
        """
        return

class BasePreprocessor(BasePlugin):
    """
    A preprocessing plugin should implement a run() function

    """
    # Default behavior for run()
    INPUT = 'reads'
    OUTPUT = 'reads'

    def __call__(self, settings, job_data):
        self.run_checks(settings, job_data)
        logging.info("{} Settings: {}".format(self.name, settings))
        self.outpath = self.create_directories(job_data)
        self.init_settings(settings, job_data)
        valid_files = self.get_valid_reads(job_data)
        output = self.run(valid_files)

        self.out_module.close()
        return output

    # Must implement run() method
    @abc.abstractmethod
    def run(self, reads):
        """
        Input: READS: list of dicts contain file and read info
        Output: Updated READS (each read['files'] list should be updated 
        with the new processed reads
          
        """
        return

class ModuleManager():
    def __init__(self, threads):
        self.pmanager = PluginManager()
        self.pmanager.setPluginPlaces(["plugins"])
        self.pmanager.collectPlugins()
        self.pmanager.locatePlugins()
        self.plugins = []
        if len(self.pmanager.getAllPlugins()) == 0:
            raise Exception("No Plugins Found!")
        for plugin in self.pmanager.getAllPlugins():
            plugin.threads = threads
            self.plugins.append(plugin.name)
            plugin.plugin_object.setname(plugin.name)
            print "Plugin found: {}".format(plugin.name)

    def run_module(self, module, job_data_orig, tar=False, all_data=False, reads=False):
        """
        Keyword Arguments:
        module -- name of plugin
        job_data -- dict of job parameters
        tar -- return tar of all output, rather than module.OUTPUT file
        all_data -- return module.OUTPUT and list of all files in self.outdir
        reads -- include files if module.OUTPUT == 'reads'
          Not recommended for large read files.

        """
        job_data = copy.deepcopy(job_data_orig)
        # Pass back orig file descriptor
        job_data['out_report'] = job_data_orig['out_report'] 

        if not self.has_plugin(module):
            raise Exception("No plugin named {}".format(module))
        plugin = self.pmanager.getPluginByName(module)
        settings = plugin.details.items('Settings')
        plugin.plugin_object.update_settings(job_data)
        output = plugin.plugin_object(settings, job_data)
        if tar:
            return plugin.plugin_object.tar_output(job_data['job_id'])
        if all_data:
            if not reads and plugin.plugin_object.OUTPUT == 'reads':
                #Don't return all files from plugins that output reads 
                data = []
            else:
                data = plugin.plugin_object.get_all_output_files()
            return output, data
        return output

    def output_type(self, module):
        return self.pmanager.getPluginByName(module).plugin_object.OUTPUT

    def input_type(self, module):
        return self.pmanager.getPluginByName(module).plugin_object.INPUT

    def has_plugin(self, plugin):
        if not plugin in self.plugins:
            logging.error("{} plugin not found".format(plugin))
            return False
        return True


