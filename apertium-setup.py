#!/usr/bin/env python3

import sys, os, argparse
import xml.etree.ElementTree as ET

PC_FILE = '''prefix={prefix}
exec_prefix={prefix}
srcdir={prefix}/share/apertium/{BASENAME}

Name: {BASENAME}
Description: {Description}
Version: {VERSION}
'''

INSTALL_RECIPE = '''
install-pc: $(BASENAME).pc
	$(MKDIR_P) $(DESTDIR)$(pkgconfigdir) || exit 1
	$(INSTALL) $(BASENAME).pc $(DESTDIR)$(pkgconfigdir) || exit $$?
uninstall-pc:
	test -d $(DESTDIR)$(pkgconfigdir) && \\
	test -r $(DESTDIR)$(pkgconfigdir) && \\
	cd $(DESTDIR)$(pkgconfigdir) && rm -f $(BASENAME).pc

DATA = $(SOURCES) $(TARGETS) $(CUSTOM_TARGETS) $(EXTRA_TARGETS)
install-data: all
	$(MKDIR_P) $(DESTDIR)$(datadir) || exit 1
	$(INSTALL) $(DATA) $(DESTDIR)$(datadir) || exit $$?
uninstall-data:
	test -d $(DESTDIR)$(datadir) && test -r $(DESTDIR)$(datadir) && \\
	cd $(DESTDIR)$(datadir) && rm -f $(DATA)

install-modes: $(INSTALL_MODES)
	apertium-gen-modes -f modes.xml $(datadir)
	$(MKDIR_P) $(DESTDIR)$(modesdir) || exit 1
	$(INSTALL) $(INSTALL_MODES) $(DESTDIR)$(modesdir) || exit $$?
	rm $(INSTALL_MODES)
uninstall-modes:
	test -d $(DESTDIR)$(modesdir) && test -r $(DESTDIR)$(modesdir) && \\
	cd $(DESTDIR)$(modesdir) && rm -f $(INSTALL_MODES)

install: install-pc install-data install-modes
uninstall: uninstall-pc uninstall-data uninstall-modes

.PHONY: install install-pc install-data install-modes
.PHONY: uninstall uninstall-pc uninstall-data uninstall-modes
'''

# target => [ ( [ sources ], [ intermediate targets ] recipe ) ]

MONO_RECIPES = {
    'automorf.bin': [
        ([['dix', 'acx']],
         [],
         '{LANG}.automorf.bin: {BASENAME}.{LANG}.dix {BASENAME}.{LANG}.acx\n'
         '\tapertium-validate-dictionary $<\n'
         '\tlt-comp lr $< $@ {BASENAME}.{LANG}.acx'),
        ([['dix']],
         [],
         '{LANG}.automorf.bin: {BASENAME}.{LANG}.dix\n'
         '\tapertium-validate-dictionary $<\n'
         '\tlt-comp lr $< $@'),
        ([['lexc'], ['lexd']],
         [],
         '{LANG}.automorf.bin: {LANG}.automorf.att.gz .deps/.d\n'
         '\tzcat < $< > .deps/{LANG}.automorf.att\n'
         '\tlt-comp lr .deps/$(LANG1).automorf.att $@')
    ],
    'autogen.bin': [
        ([['dix', 'acx']],
         [],
         '{LANG}.autogen.bin: {BASENAME}.{LANG}.dix {BASENAME}.{LANG}.acx\n'
         '\tapertium-validate-dictionary $<\n'
         '\tlt-comp rl $< $@ {BASENAME}.{LANG}.acx'),
        ([['dix']],
         [],
         '{LANG}.autogen.bin: {BASENAME}.{LANG}.dix\n'
         '\tapertium-validate-dictionary $<\n'
         '\tlt-comp rl $< $@'),
        ([['lexc'], ['lexd']],
         [],
         '{LANG}.automorf.bin: {LANG}.automorf.att.gz .deps/.d\n'
         '\tzcat < $< > .deps/{LANG}.automorf.att\n'
         '\tlt-comp lr .deps/$(LANG1).automorf.att $@')
    ],
    'automorf.att.gz': [
        ([['dix']],
         ['{_current_name_}.automorf.bin'],
         '{LANG}.automorf.att.gz: {LANG}.automorf.bin\n'
         '\tlt-print $< | gzip -9 -c -n > $@'
        )
    ],
    'autogen.att.gz': [
        ([['dix']],
         ['{_current_name_}.autogen.bin'],
         '{LANG}.autogen.att.gz: {LANG}.autogen.bin\n'
         '\tlt-print $< | gzip -9 -c -n > $@'
        )
    ],
    'autopgen.bin': [
        ([['post-dix']],
         [],
         '{LANG}.autopgen.bin: {BASENAME}.post-{LANG}.dix\n'
         '\tapertium-validate-dictionary $<\n'
         '\tlt-comp lr $< $@')
    ],
    'rlx.bin': [
        ([['rlx']],
         [],
         '{LANG}.rlx.bin: {BASENAME}.{LANG}.rlx\n'
         '\tcg-comp $< $@')
    ]
}

def get_programs():
    defaults = {
        'MKDIR_P': '/bin/mkdir -p',
        'INSTALL': '/usr/bin/install -c -m 644',
        'SHELL': '/bin/bash'
    }
    # there's probably some situation where these could break
    # and we should check for that, but for the moment eh
    # -DGS
    return defaults

def gen_pc(settings, pcfile):
    with open(pcfile, 'w') as out:
        out.write(PC_FILE.format(**settings))

def get_recipes_mono(settings):
    base = settings['BASENAME']
    lg = settings['LANG']
    todo = settings['TARGETS'] + settings.get('EXTRA_TARGETS', [])
    sources = settings['SOURCES']
    source_types = []
    for s in sources:
        source_types.append(s.replace(base+'.', '').replace(lg+'.', ''))
    custom = settings.get('CUSTOM_TARGETS', [])
    recipes = {}
    print('TODO', todo)
    print('sources', sources)
    print('types', source_types)
    while todo:
        fname = todo.pop()
        if fname in recipes or fname in sources or fname in custom:
            continue
        ftype = fname.replace(settings['BASENAME']+'.', '')
        cur_var = settings['LANG']
        for v in settings.get('VAR', []):
            if cur_var + '_' + v in ftype:
                cur_var += '_' + v
                break
        ftype = ftype.replace(cur_var+'.', '')
        if ftype not in MONO_RECIPES:
            print('ERROR: Could not find recipe for %s' % fname)
            sys.exit(1)
        for srcs, dep, rec in MONO_RECIPES[ftype]:
            if any(all(s in source_types for s in src) for src in srcs):
                for d in dep:
                    todo.append(d.format(_current_name_=cur_var, **settings))
                recipes[fname] = rec.format(_current_name_=cur_var, **settings)
                break
        else:
            print('ERROR: Sources required for %s not found' % fname)
            sys.exit(1)
    return recipes

def get_recipes_bil(settings):
    return {}

def gen_makefile(settings, makefile):
    with open(makefile, 'w') as out:
        for s in sorted(settings.keys()):
            if s == 'CUSTOM' or s.startswith('_'):
                continue
            if isinstance(settings[s], str):
                out.write('%s = %s\n' % (s, settings[s]))
            elif isinstance(settings[s], list):
                out.write('%s = %s\n' % (s, ' '.join(settings[s])))
        out.write('\n')
        recipes = None
        if 'LANG' in settings:
            recipes = get_recipes_mono(settings)
        else:
            recipes = get_recipes_bil(settings)
        clean = []
        for f in sorted(recipes.keys()):
            clean.append(f)
            out.write(recipes[f] + '\n\n')
        out.write('Makefile: $(BASENAME).meta modes.xml\n')
        out.write('\tapertium-setup $(BASENAME).meta modes.xml\n')
        out.write('$(BASENAME).pc: Makefile\n\n')
        out.write('CLEANFILES = $(TARGETS) $(CUSTOM_TARGETS) $(EXTRA_TARGETS) $(CUSTOM_CLEAN)\n')
        out.write('clean:\n\t-test -z "$(CLEANFILES)" || rm -f $(CLEANFILES)\n')
        out.write('\t-rm -rf .deps modes *.mode\n\n')
        out.write('all: Makefile $(BASENAME).pc $(CLEANFILES)\n\n')
        out.write('.PHONY: all clean\n\n')
        out.write(INSTALL_RECIPE)
        if 'CUSTOM' in settings:
            out.write('\n\n')
            out.write(settings['CUSTOM'])
            out.write('\n')

def tokenize(line):
    toks = []
    cur = ''
    escape = False
    for c in line:
        if escape:
            cur += c
            escape = False
        elif c == '\\':
            escape = True
        elif c.isspace():
            if cur:
                toks.append(cur)
                cur = ''
        elif c in ':=|':
            if cur:
                toks.append(cur)
                cur = ''
            toks.append(c)
        elif c == '#' and not cur:
            break
        else:
            cur += c
    if cur:
        toks.append(cur)
    # simply ignore trailing backslashes for now
    return toks

def read_meta(fname):
    with open(fname) as infile:
        settings = get_programs()
        custom = False
        for line_number, line in enumerate(infile, start=1):
            if custom:
                settings['CUSTOM'] += line
                continue
            toks = tokenize(line)
            if len(toks) == 0:
                continue
            elif len(toks) >= 3 and toks[1] == '=':
                if toks[0] in settings:
                    print('WARNING: %s set multiple times - using later definition.' % toks[0])
                settings[toks[0]] = ' '.join(toks[2:])
            elif len(toks) >= 3 and toks[1] == ':':
                if toks[0] not in settings:
                    settings[toks[0]] = []
                settings[toks[0]] += toks[2:]
            elif toks == ['CUSTOM']:
                settings['CUSTOM'] = ''
                custom = True
            else:
                print('WARNING: Unable to interpret line %s, skipping.' % line_number)
        return settings

def setup(args):
    parser = argparse.ArgumentParser(
        description='Generate Makefiles for Apertium languages and translation pairs'
    )
    parser.add_argument('meta_path')
    parser.add_argument('modes_path')
    parser.add_argument('--prefix', default='/usr/local')
    parser.add_argument('--with-lang1')
    parser.add_argument('--with-lang2')
    args = parser.parse_args(args)
    settings = read_meta(args.meta_path)
    settings['prefix'] = args.prefix
    mono = ('LANG' in settings)
    pair = ('LANG1' in settings and 'LANG2' in settings)
    if mono and pair:
        print('Metadata file cannot specify both LANG and LANG1,LANG2.')
        sys.exit(1)
    elif not mono and not pair:
        print('Metadata file must either specify LANG or both LANG1 and LANG2.')
        sys.exit(1)
    elif mono:
        lg = settings['LANG']
        settings.setdefault('BASENAME', 'apertium-' + lg)
        name = settings.setdefault('LANG_NAME', lg)
        settings.setdefault('Description', 'Finite-state morphological transducer and constraint grammar for ' + name)
        if 'EXTRA_TARGETS' not in settings:
            settings['EXTRA_TARGETS'] = []
        settings['EXTRA_TARGETS'] += [
            '{LANG}.automorf.att.gz'.format(**settings),
            '{LANG}.autogen.att.gz'.format(**settings)
        ]
    else:
        lg1 = settings['LANG1']
        lg2 = settings['LANG2']
        settings.setdefault('BASENAME', 'apertium-%s-%s' % (lg1, lg2))
        name1 = settings.setdefault('LANG1_NAME', lg1)
        name2 = settings.setdefault('LANG2_NAME', lg2)
        settings.setdefault('Description', 'Apertium-based %s-%s machine translation' % (name1, name2))
    v = settings.get('VERSION', '').split('.')
    if len(v) != 3 or not all(x.isdigit() for x in v):
        print('Metadata file must specify VERSION in the from Major.Minor.Patch.')
        sys.exit(1)
    modes = ET.parse(args.modes_path).getroot()
    settings['INSTALL_MODES'] = []
    if 'TARGETS' in settings:
        print('Build targets not mentioned in modes.xml should use EXTRA_TARGETS, not TARGETS')
        sys.exit(1)
    trg = []
    for mode in modes:
        if mode.attrib.get('install', 'no') == 'yes':
            settings['INSTALL_MODES'].append(mode.attrib['name'] + '.mode')
            for f in mode.iter('file'):
                if f.attrib['name'] not in settings['SOURCES']:
                    trg.append(f.attrib['name'])
        else:
            for fn in mode.iter('file'):
                f = f.attrib['name']
                if '/' not in f and f not in settings['SOURCES']:
                    trg.append(f)
    settings['TARGETS'] = list(set(trg))
    settings['datadir'] = '{prefix}/share/apertium/{BASENAME}/'.format(**settings)
    settings['modesdir'] = args.prefix + '/share/apertium/modes/'
    settings['pkgconfigdir'] = args.prefix + '/share/pkgconfig/'
    gen_pc(settings, settings['BASENAME']+'.pc')
    gen_makefile(settings, 'Makefile')

if __name__ == '__main__':
    setup(sys.argv[1:])
