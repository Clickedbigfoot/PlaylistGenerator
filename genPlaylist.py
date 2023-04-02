"""
Purpose: generate an xspf playlist file based on the specified config file.
The included playlist.cfg file serves as a good template for how to
configure this.

By default, it uses playlist.cfg.
However, other config files and multiple config files can be specified.
If multiple config files are specified, they are processed in left to
right order.

Sample usage:
python genPlaylist.py config1.cfg config2.cfg config3.cfg

@TODO implement maximum
@TODO implement all:dir
@TODO implement random for general
@TODO enhanced missing files from artists
@TODO missing files from general
"""
import configparser
import os
import sys
import random
from tinytag import TinyTag
from tinytag.tinytag import TinyTagException

# Keys to section fields
INCLUDE_KEY = "include"
EXCLUDE_KEY = "exclude"
RANDOM_KEY = "random"
OUTPUT_PATH_KEY = "outputPath"

# Parts of the playlist file (.xspf)
PLAYLIST_HEADERS = '<?xml version="1.0" encoding="UTF-8"?>\n<playlist version="1" xmlns="http://xspf.org/ns/0/">\n\t<trackList>\n'
PLAYLIST_END = '\t</trackList>\n</playlist>'
PLAYLIST_ENTRY_TEMPLATE = '\t\t<track><location>file:///{}</location><title>{}</title></track>\n'


class SectionFiles:
    """
    Compiles all files specified in a config section's directories.

    Initialize with the value from a config file section's dirs field.
    This then compiles all media files in those directories with their
    1) File name
    2) Absolute path
    3) Contributing Artists
    to help search for files later on
    """
    pass


class PlaylistGenerator:
    """Generates a playlist to a config file's specifications."""

    def __init__(self, configFile):
        """
        Init.

        @param configFile: string of path to config file
        """
        self.configFile = configFile
        self.config = configparser.ConfigParser()
        self.config.read(configFile)

    def stripAll(self, string):
        """Strip whitespace and quotes."""
        if isinstance(string, str):
            string = string.strip().strip("'\"")
        return string

    def getArtist(self, filePath):
        """
        Get the artists' names.

        @param filePath: path to the file in question
        @return list of strings of the artist name(s),
            or empty list if unable to get that information
        """
        try:
            tag = TinyTag.get(filePath)
        except TinyTagException:
            print("warning: could not get artist for {}".format(filePath))
            return []
        if tag.artist is None:
            return []
        return tag.artist.split("/")

    def parseFileList(self, section, key, paths, names):
        """
        Parse list of files in section field.

        Populates sets depending on if the element is a valid path or not
        @param section: dict representing the section in question
        @param key: key to dict representing the field name
        @param paths: set of absolute paths of files
        @param names: set of names of files
        """
        if key in section:
            # Iterate through each entry in include
            for entry in section[key].strip().split(","):
                # Strip whitespace and any quotations for paths
                entry = self.stripAll(entry)

                # Add file if it is a path, otherwise add it to fileNames
                if os.path.isfile(entry):
                    paths.add(os.path.abspath(entry))
                elif entry != "":
                    names.add(entry)

    def addSpecifiedFiles(self, section, filePaths, excludePaths, fileNames, excludeNames):
        """
        Populate sets with their intended values from the section.

        Reads the section and populates filenames into the rules sets. Also adds
        absolute paths of specified files automatically, provided the maximum is
        not yet reached.

        @param section: section to read from
        @param filePaths: set of absolute paths of files to add to the playlist
        @param excludedPaths: set of absolute paths of files to exclude from the playlist
        @param fileNames: set of names of files to add to the playlist
        @param excludeNames: set of names of files to exclude from the playlist
        """
        # Verify the section exists
        if section not in self.config:
            return

        # Populate filePaths and fileNames
        self.parseFileList(self.config[section], INCLUDE_KEY, filePaths, fileNames)

        # Populate excludePaths and excludeNames
        self.parseFileList(self.config[section], EXCLUDE_KEY, excludePaths, excludeNames)

    def getArtistRules(self, filePaths, excludePaths):
        """
        Generate artist rules dict and process certain files in advance.

        @param filePaths: set of file paths added to the playlist
        @param excludedPaths: set of absolute paths of files to exclude from the playlist
        @return dict mapping each artist to their respective rules and state.
            this dict should also have a list that will contain absolute paths
            of files to be randomly chosen if they are not otherwise selected
            or excluded
        """
        # Dict of all artists' rules
        rules = {}

        # Iterate through each artist
        for section in self.config.keys():
            # Skip General section
            if section == "General":
                continue

            # Create dict of rules for this artist
            # These are whether or not all files should be added,
            # remaining names of files to be added,
            # names of files to exclude,
            # and a list of paths of files to add afterwards
            artistRules = {"addAll": False,
                           "fileNames": set(),
                           "excludeNames": set(),
                           "random": []}

            # Populate sets
            self.addSpecifiedFiles(section, filePaths, excludePaths,
                                   artistRules["fileNames"], artistRules["excludeNames"])

            # Assume we want all files if include field is empty or missing
            # and no random number is specified
            if ((INCLUDE_KEY not in self.config[section]
                    or len(self.config[section][INCLUDE_KEY].strip()) == 0)
                    and RANDOM_KEY not in self.config[section]):
                artistRules["addAll"] = True

            # Add to total rules dict
            rules[section] = artistRules

        return rules

    def processArtistRules(self, rules, artist, filePaths, filename, filePath):
        """
        Process file through respective artist rules.

        Add file to filePaths if rules allow.
        @param rules: dict of the artist's rules
        @param artist: string of artist name
        @param filePaths: set of absolute paths of files to add to the playlist
        @param filename: name of file in question
        @param filePath: absolute path of file in question
        """
        # Check if file is excluded
        if filename in rules["excludeNames"]:
            # File is excluded
            return

        # Check if file is included
        if rules["addAll"] or filename in rules["fileNames"]:
            filePaths.add(filePath)

            # Remove filename from remaining files to add
            if filename in rules["fileNames"]:
                rules["fileNames"].remove(filename)
        else:
            # Not specified - add to random pile for later
            rules["random"].append(filePath)

    def writeToPlaylist(self, filePaths):
        """
        Write to playlist file.

        @param filePaths: list of files' absolute paths to write to playlist
        """
        # Verify that the output path exists
        if "General" not in self.config or OUTPUT_PATH_KEY not in self.config["General"]:
            print("error: can't find output file path in General section")
            return

        # Write playlist file
        with open(self.config["General"][OUTPUT_PATH_KEY], "w+") as outputFile:
            # Write headers
            outputFile.write(PLAYLIST_HEADERS)

            # Write all of the files
            for filePath in filePaths:
                # Get name of file
                fileName = os.path.basename(filePath)

                # Write entry
                outputFile.write(PLAYLIST_ENTRY_TEMPLATE.format(filePath, fileName))

            # Write end of playlist file
            outputFile.write(PLAYLIST_END)

    def genPlaylist(self):
        """
        Generate playlist based on config file.

        @return 0 if successful, 1 otherwise
        """
        print('Starting {}'.format(self.configFile))
        # Set of absolute paths of files to add to the playlist
        filePaths = set()

        # Set of absolute paths of files to exclude from filePaths
        excludePaths = set()

        # Set of names of files to add to or exclude from filePaths
        fileNames = set()
        excludeNames = set()

        # List of random general files' absolute paths to add later if dictated
        randomGeneral = []

        # Create rules specific to artists
        # Also adds files with their paths specified in the artist sections
        artistRules = self.getArtistRules(filePaths, excludePaths)

        # Add any files with their paths specified in general section
        # Also update the excluded paths for General
        self.addSpecifiedFiles("General", filePaths, excludePaths, fileNames, excludeNames)

        # Go through each file in general directories
        if "dirs" in self.config["General"]:
            for directory in self.config["General"]["dirs"].strip().split(","):
                # Strip away any whitespace or quotation marks
                directory = self.stripAll(directory)

                # Check that this is a valid directory
                if not os.path.isdir(directory):
                    # Skip invalid directory
                    print("error: invalid directory {}".format(directory))
                    continue

                # Iterate through each file in this directory
                for filename in os.listdir(directory):
                    # Get the absolute path
                    filePath = os.path.abspath(os.path.join(directory, filename))

                    # Skip non-files (Ex: subdirectories)
                    if not os.path.isfile(filePath):
                        continue

                    # Skip if this has already been added or should be excluded
                    if (filePath in filePaths or filePath in excludePaths
                            or filename in excludeNames):
                        continue

                    # Determine artists if any and apply correct rules
                    artists = self.getArtist(filePath)
                    hadArtistRules = False
                    for artist in artists:
                        if artist in artistRules:
                            # We have specific rules for this file
                            hadArtistRules = True
                            self.processArtistRules(artistRules[artist], artist, filePaths,
                                                    filename, filePath)
                            # @TODO is this break a good idea for multiple artist files?
                            break

                    # Apply general rules if no specific artist rules applied
                    if not hadArtistRules:
                        # @TODO implement ALL dir rules
                        if filename in fileNames:
                            # Filename is specified
                            filePaths.add(filePath)

                            # Remove from fileNames to keep track of files that haven't been added
                            fileNames.remove(filename)
                        else:
                            # File is not specified, add to random pile
                            randomGeneral.append(filePath)

        # Add random files
        for artist in artistRules:
            # Check if any random files are requested
            if RANDOM_KEY not in self.config[artist]:
                continue

            # Add random files to filePaths
            try:
                nRandom = int(self.config[artist][RANDOM_KEY])
            except Exception:
                # Invalid random number
                print("error: invalid number of random files for {}".format(artist))
                continue

            # @TODO handle issue where size of list being sampled is smaller than number of samples requested
            # @TODO additional bug when only random is specified for an artist, no include/exclude
            for filePath in random.sample(artistRules[artist]["random"], nRandom):
                filePaths.add(filePath)
                print("Adding random {}".format(filePath))

        # Print missing files
        for artist in artistRules:
            if len(artistRules[artist]["fileNames"]) > 0:
                for fileName in list(artistRules[artist]["fileNames"]):
                    print("warning: missing {} from {}".format(fileName, artist))

        # Write file
        self.writeToPlaylist(filePaths)
        print("Finished {}".format(self.configFile))


def main(args):
    """Follow main flow."""
    for arg in args:
        # Verify valid config file
        if not os.path.isfile(arg):
            print("warning: skipping invalid config file {}".format(arg))
            continue

        # Create PlaylistGenerator object
        gen = PlaylistGenerator(arg)
        gen.genPlaylist()

if __name__ == "__main__":
    # @TODO implement arg parser
    if len(sys.argv) < 2:
        print("error: no config files specified")
        exit()
    main(sys.argv[1:])