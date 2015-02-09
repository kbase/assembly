import glob
import logging
import os
from plugins import BaseAssembler
from yapsy.IPlugin import IPlugin

class SpadesAssembler(BaseAssembler, IPlugin):
    new_version = True

    def run(self):
        """
        Build the command and run.
        Return list of contig file(s)

        SPAdes takes as input forward-reverse paired-end reads as well as single (unpaired) reads in FASTA or FASTQ format. However, in order to run read error correction, reads should be in FASTQ format. Currently SPAdes accepts only one paired-end library, which can be stored in several files or several pairs of files. The number of unpaired libraries is unlimited.
        """

        cmd_args = [self.executable]
        lib_num = 1
        for readset in self.data.readsets_paired:
            if lib_num > 5:
                print '> 5 pairs not supported!'
                self.out_module.write('> 5 pairs not supported!')
                break
            if len(readset.files) == 1: # Interleaved
                cmd_args += ['--pe{}-12'.format(lib_num), readset.files[0]]
            elif len(readset.files) >= 2: # 2 Files
                cmd_args += ['--pe{}-1'.format(lib_num), readset.files[0],
                             '--pe{}-2'.format(lib_num), readset.files[1]]
                for extra in readset.files[2:]:
                    self.out_module.write('WARNING: Not using {}'.format(extra))
                    print('WARNING: Not using {}'.format(extra))
            else:
                raise Exception('Spades module file error')
            lib_num += 1

        for readset in self.data.readsets_single:
            single_num = lib_num if lib_num < 5 else 5
            cmd_args += ['--pe{}-s'.format(single_num), readset.files[0]]
            lib_num += 1

        if self.only_assembler == 'True':
            cmd_args.append('--only-assembler')

        if self.read_length == 'medium' or self.read_length == '150':
            cmd_args += ['-k', '21,33,55,77']

        if self.read_length == 'medium2' or self.read_length == '200':
            cmd_args += ['-k', '21,33,55,77,99']

        if self.read_length == 'long' or self.read_length == '250':
            cmd_args += ['-k', '21,33,55,77,99,127']

        cmd_args += ['-o', self.outpath]
        cmd_args += ['-t', self.process_threads_allowed]  # number of threads = 4
        if self.mismatch_correction == 'True':
            cmd_args.append('--mismatch-correction')
        if self.careful == 'True':
            cmd_args.append('--careful')
        self.arast_popen(cmd_args)
        contigs = os.path.join(self.outpath, 'contigs.fasta')
        scaffolds = os.path.join(self.outpath, 'scaffolds.fasta')

        output = {}
        if os.path.exists(contigs):
            output['contigs'] = [contigs]
        if os.path.exists(scaffolds):
            output['scaffolds'] = [scaffolds]
        return output
