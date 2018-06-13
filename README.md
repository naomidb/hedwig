# hedwig
Automated process to get information from Web of Science into VIVO

## Configuring Your Config
The config file is absolutely vital to running hedwig. An example is included, but you must update it. The config file can be named anything, as you will pass the file in when you run hedwig.

*email/password*: If your VIVO requires credentials (as many do, especially for updating), place that information here.

*update_endpoint/query_endpoint*: Write the query and update endpoints here.

*namespace*: The uris for individuals in VIVO are made up of two parts- a default name space and an n number ('n' + a random number).

*input_file*: The path to the bibtex file you will process when using the `--bibtex` flag.

*folder_for_logs*: The folder where logs from each hedwig run are stored. If you use the `--rdf` flag, the rdf file to be uploaded will also be stored here. Hedwig will further organize logs based on date within this folder.

*filter_folder*: The path to the folder which contains the various filter files. The format for the filters will be explained below.

*wos_credentials*: If you are using the `--query` flag, you will need to use the WOS api, which requires your credentials. The credentials should be formatted as `Username:Password` encoded into base 64. If you are only using the `--bibtex` option, you will not need this.

*database/database_port/database_user/database_pw*: Future versions will allow you to store the data you input into a database. For now, you can ignore this section.

## Fixing Your Filters
There are three required filter files (although they can be empty). The first is `general_filter.yaml`. This filter contains general things to be changed (e.g. "Adv ": "Advanced "). The filter should be a dictionary with the key being `abbrev_table` and the value being another dictionary of the actual words/abbreviations to be changed. **Please note** that every item in this inner-dictionary (on both sides of the colons) must end with a blank space. This is to prevent the word "Advanced" from becoming "Advancedanced".

```
abbrev_table:
      " & ": " and "
      "'S ": "'s "
      " A ": " a "
      "Aav ": "AAV "
      "Aca ": "Academy "
      "Acad ": "Academy "
      "Admn ": "Administration "
      "Adv ": "Advanced "
```
The second and third filters are `publisher_filter.yaml` and `journal_filter.yaml`, which both use the same format. First, write the way the publisher/journal appears in the bibtex file/api response. Make sure you write the name in all capital letters. Then write a colon and, in double quotes, the name as you would like it to appear when uploaded to VIVO.

```
STRANGE JOURN NAME: "Journal of Strange Names"
```

## Handling Hedwig
As of now, hedwig can only be used with the -b bibtex option. You will need to go to the Web of Science site and download the bibtex file before running hedwig. Hedwig uses Python3. When running hedwig, you must select one from two pairs of flags.

`-q --query/-b --bibtex` This flag clarifies where the input is coming from. The options are to query the WOS api directly or to use an input file (written in the config file). The query option is not currently supported.

`-a --api/-r --rdf` This flag clarifies how you will deliver the information to VIVO. The api option means you will use the VIVO api to upload data. The rdf option means the triples will be written to a file, which you can then upload. If you suspect you may need to get rid of the information you are uploading in the future, I stronly advise that you use the rdf option.

After choosing two of the above flags, you will write the path to the config file.

```python hedwig.py -ba config.yaml```
