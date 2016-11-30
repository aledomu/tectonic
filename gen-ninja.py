#! /usr/bin/env python
# -*- mode: python; coding: utf-8 -*-
# Copyright 2016 Peter Williams and collaborators.
# Licensed under the MIT License.

from __future__ import absolute_import, division, print_function, unicode_literals

import os, sys
from pwkit import io, ninja_syntax


config = {
    'build_name': 'BUILD',
    'base_cflags': '-g -O0 -Wall',
    # pkg-config --cflags fontconfig harfbuzz harfbuzz-icu freetype2 graphite2 libpng zlib icu-uc poppler
    'pkgconfig_cflags': '-I/usr/include/freetype2 -I/usr/include/libpng16 -I/usr/include/harfbuzz -I/usr/include/glib-2.0 -I/usr/lib64/glib-2.0/include -I/usr/include/freetype2 -I/usr/include/libpng16 -I/usr/include/poppler',
    'pkgconfig_libs': '-lfontconfig -lharfbuzz-icu -lharfbuzz -lfreetype -lgraphite2 -lpng16 -lz -licuuc -licudata -lpoppler',
    # output by rustc:
    'kpz_libs': '-lutil -ldl -lpthread -lgcc_s -lc -lm -lrt -lutil',
}


def inner (top, w):
    # build.ninja gen rule.

    w.comment ('Automatically generated.')

    w.rule ('regen',
            command='./gen-ninja.py $in',
            description='GEN $out',
            generator=True)
    w.build ('build.ninja', 'regen', implicit='gen-ninja.py')

    # Base rules

    w.rule ('cc',
            command='gcc -c -o $out -MT $out -MD -MP -MF $out.d $cflags $in',
            deps='gcc',
            depfile='$out.d',
            description='CC $out')

    w.rule ('cxx',
            command='g++ -c -o $out -MT $out -MD -MP -MF $out.d $cflags $in',
            deps='gcc',
            depfile='$out.d',
            description='CXX $out')

    w.rule ('cargo',
            command='cd $dir && cargo build $args',
            description='CARGO $out')

    w.rule ('staticlib',
            command='ar cru $out $in',
            description='AR $out')

    w.rule ('executable',
            command='g++ -o $out $in $libs',
            description='LINK $out')

    # build dir

    builddir = top / config['build_name']

    # utility.

    def compile (sources=None, bldprefix=None, rule=None, **kwargs):
        objs = []

        for src in sources:
            obj = builddir / (bldprefix + src.name.replace ('.c', '.o'))
            w.build (
                str(obj), rule,
                inputs = [str(src)],
                variables = kwargs,
            )
            objs.append (str (obj))

        return objs

    def staticlib (sources=None, basename=None, rule=None, order_only=[], implicit=[], **kwargs):
        lib = builddir / ('lib' + basename + '.a')
        objs = compile (
            sources = sources,
            bldprefix = basename + '_',
            rule = rule,
            **kwargs)
        w.build (str(lib), 'staticlib',
                 inputs = objs,
                 order_only = order_only,
                 implicit = implicit,
        )
        return lib

    def executable (output=None, sources=None, rule=None, slibs=[], libs='', **kwargs):
        """slibs are locally-built static libraries. libs is passed to the linker
        command line.

        """
        objs = compile (
            sources = sources,
            bldprefix = output.name + '_',
            rule = rule,
            **kwargs)
        objs += map (str, slibs)
        w.build (str(output), 'executable',
                 inputs = objs,
                 variables = {'libs': libs})
        return str(output) # convenience

    # kpsezip -- kpathsea workalike written in Rust

    libkpz = top / 'kpsezip' / 'target' / 'debug' / 'libkpsezip.a'

    kpz_inputs = [
        top / 'kpsezip' / 'Cargo.toml',
        top / 'kpsezip' / 'Cargo.lock',
    ]
    for src in (top / 'kpsezip' / 'src').glob ('*.rs'):
        kpz_inputs.append (src)

    w.build (
        str(libkpz), 'cargo',
        inputs = [str(f) for f in kpz_inputs],
        variables = {
            'dir': 'kpsezip',
            'args': '-q',
        }
    )

    # tectonic-compat

    cflags = '-DHAVE_CONFIG_H -D__SyncTeX__ -Itectonic -I. %(pkgconfig_cflags)s %(base_cflags)s' % config
    objs = []

    def tc_c_sources ():
        for src in (top / 'tectonic').glob ('*.c'):
            if src.name == 'NormalizationData.c':
                continue
            yield src

    for src in tc_c_sources ():
        obj = builddir / src.name.replace ('.c', '.o')
        w.build (
            str(obj), 'cc',
            inputs = [str(src)],
            variables = {'cflags': cflags},
        )
        objs.append (str (obj))

    for src in (top / 'tectonic').glob ('*.cpp'):
        obj = builddir / src.name.replace ('.cpp', '.o')
        w.build (
            str(obj), 'cxx',
            inputs = [str(src)],
            variables = {'cflags': cflags},
        )
        objs.append (str (obj))

    objs += map (str, [libkpz])
    libs = '%(pkgconfig_libs)s %(kpz_libs)s -lz' % config

    w.build (str(builddir / 'tectonic-compat'), 'executable',
             inputs = objs,
             variables = {'libs': libs},
    )


def outer (args):
    top = io.Path ('')
    me = io.Path (sys.argv[0]).parent

    with (me / 'build.ninja').open ('wt') as f:
        w = ninja_syntax.Writer (f)
        inner (top, w)


if __name__ == '__main__':
    import sys
    outer (sys.argv[1:])
