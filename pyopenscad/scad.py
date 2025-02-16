#!/usr/bin/env python3
# Analyzer is part of:
# SCA2D Copyright (C) 2007 Julian Stirling
# This program comes with ABSOLUTELY NO WARRANTY; for details type `show w'.
# This is free software, and you are welcome to redistribute it
# under certain conditions; type `show c' for details.

import os
from lark import Lark
from lark.exceptions import LarkError
from sca2d.outerscope import OuterScope, NonFileOuterScope
from sca2d.scadclasses import UseIncStatment, DummyTree
from sca2d.utilities import locate_file
from sca2d.messages import Message
# See example at <https://gitlab.com/bath_open_instrumentation_group/
#   sca2d/-/blob/master/sca2d/sca2d.py>



# See example at <https://gitlab.com/bath_open_instrumentation_group/
#   sca2d/-/blob/master/sca2d/sca2d.py>
class ScadParser():
    def __init__(self, grammar_path):
        self._parser = self._create_parser(grammar_path)

    def _create_parser(self, grammar_path):
        with open(grammar_path, 'r') as ins:
            grammar = ins.read()
        return Lark(grammar, propagate_positions=True)

    def parse(self, data):
        '''
        The input should be a string containing all of the file's code.
        '''
        return self._parser.parse(data)


class ScadAnalyser:
    def __init__(self, grammar_path, verbose=False):
        self._parser = ScadParser(grammar_path)
        self._parsed_files = {}
        self._verbose = verbose

    def _parse_file(self, filename):
        '''
        Parses the input file returns an OuterScope object. This object is also
        stored by the Analyzer for future use.
        '''
        if self._verbose:
            print(f'parsing {filename}')
        try:
            with open(filename, 'r') as file_obj:
                scad_code = file_obj.read()
        except (OSError, IOError):
            return Message(filename, "F0002", DummyTree())
        tree = self._parse_code(scad_code, filename)
        if isinstance(tree, Message):
            #_parse_code may return a Fatal message instead of a tree
            #return it to be handled later
            return tree
        self._parsed_files[filename] = OuterScope(tree, scad_code, filename)
        return self._parsed_files[filename]

    def _parse_code(self, scad_code, filename="INPUT_CODE"):
        '''
        Parses the scad code and returns the parse tree
        '''
        try:
            tree = self._parser.parse(scad_code)
        except LarkError as error:
            err_str = "\n"+str(error)
            err_str = err_str.replace('\n', '\n   - ')
            return Message(filename, "F0001", DummyTree(), [err_str])
        return tree

    def analyse_file(self, filename, output_tree=False, ignore_list=None):
        """
        Run sca2d on the input file analysing all code and printing errors.
        Returns false only on a fatal error, else returns true.
        """
        #set defaults before running

        scope = self.get_scope_from_file(filename)
        [success, all_messages] = self.analyse_scope(scope, ignore_list=ignore_list)

        if success and output_tree:
            if filename.endswith('.scad'):
                out_file = filename[:-1]+'2d'
            else:
                out_file = filename+'.sca2d'
            with open(out_file, 'w') as file_obj:
                file_obj.write(scope.tree.pretty())
        return [success, all_messages]

    def analyse_code(self, scad_code, ignore_list=None):
        """
        Run sca2d on the scad code.
        Returns 2 variable, the first a boolean on whether it was a
        success and the second is a list of all messages
        """
        #set defaults before running

        tree = self._parse_code(scad_code)
        if isinstance(tree, Message):
            #_parse_code may return a Fatal message instead of a tree
            # Return that the analysis failed
            return False, [tree]
        scope = NonFileOuterScope(tree, scad_code)
        return self.analyse_scope(scope, ignore_list=ignore_list)


    def analyse_scope(self, scope, ignore_list=None):
        """
        Run sca2d on the input scope analysing all code and printing errors.
        Returns 2 variable, the first a boolean on whether it was a
        success and the second is a list of all messages
        """
        if isinstance(scope, Message):
            # Functions that get the scope may also return a fatal error
            # message. return False and the message in a list
            return False, [scope]
        scope.analyse_tree(self)

        all_messages = scope.collate_messages()
        if ignore_list is None:
            messages = all_messages
        elif isinstance(ignore_list, list):
            messages = []
            for message in all_messages:
                if message.code not in ignore_list:
                    messages.append(message)
        else:
            raise TypeError('ingore_list should be None or a List.')

        return True, messages

    def get_scope_from_file(self, file_reference):
        '''
        Returns the OuterScope for a given file. Will parse it only if it has not already been
        parsed.
        The input can either be a string containing the file path or a UseIncStatment object
        created when a scad file parses a use or include statment.
        '''
        if isinstance(file_reference, str):
            filename = file_reference
        elif isinstance(file_reference, UseIncStatment):
            filename = locate_file(file_reference)
        else:
            raise TypeError('Analyser.parse_file cannot accept an input of type '
                            f'{type(file_reference)}')

        if filename in self._parsed_files:
            return self._parsed_files[filename]
        return self._parse_file(filename)
