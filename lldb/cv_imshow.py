# Copyright (c) 2012, Renato Florentino Garcia <fgarcia.renato@gmail.com>
#                     Stefano Pellegrini <stefpell@ee.ethz.ch>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the authors nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHORS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import lldb
import commands
import optparse
import shlex
from PIL import Image
import struct
from os import getenv
from os import path
import subprocess

def chunker(seq, size):
    return (seq[pos:pos + size] for pos in xrange(0, len(seq), size))

def get_cvmat_info(val):
    flags = val.GetChildMemberWithName('flags').GetValueAsUnsigned()
    depth = flags & 7
    channels = 1 + (flags >> 3) & 63;
    if depth == 0:
        cv_type_name = 'CV_8U'
        data_symbol = 'B'
    elif depth == 1:
        cv_type_name = 'CV_8S'
        data_symbol = 'b'
    elif depth == 2:
        cv_type_name = 'CV_16U'
        data_symbol = 'H'
    elif depth == 3:
        cv_type_name = 'CV_16S'
        data_symbol = 'h'
    elif depth == 4:
        cv_type_name = 'CV_32S'
        data_symbol = 'i'
    elif depth == 5:
        cv_type_name = 'CV_32F'
        data_symbol = 'f'
    elif depth == 6:
        cv_type_name = 'CV_64F'
        data_symbol = 'd'
    else:
        lldb.write('Unsupported cv::Mat depth\n', lldb.STDERR)
        return

    rows = val.GetChildMemberWithName('rows').GetValueAsUnsigned()
    cols = val.GetChildMemberWithName('cols').GetValueAsUnsigned()

    line_step = val.GetChildMemberWithName('step') \
            .GetChildMemberWithName('p') \
            .GetChildAtIndex(0) \
            .GetValueAsUnsigned()

    data = val.GetChildMemberWithName('data')
    data_address = unicode(data.GetValue()).encode('utf-8').split()[0]
    data_address = int(data_address, 16)

    return (cols, rows, channels, line_step, data_address, data_symbol)

def create_pil_image(process, width, height, n_channel, line_step, data_address, data_symbol):
    """ Copies the image data to a PIL image
    Args:
        width: The image width, in pixels.
        height: The image height, in pixels.
        n_channel: The number of channels in image.
        line_step: The offset to change to pixel (i+1, j) being
            in pixel (i, j), in bytes.
        data_address: The address of image data in memory.
        data_symbol: Python struct module code to the image data type.
    """
    width = int(width)
    height = int(height)
    n_channel = int(n_channel)
    line_step = int(line_step)
    data_address = int(data_address)

    error = lldb.SBError()
    memory_data = process.ReadMemory(data_address, line_step * height, error)

    # Calculate the memory padding to change to the next image line.
    # Either due to memory alignment or a ROI.
    if data_symbol in ('b', 'B'):
        elem_size = 1
    elif data_symbol in ('h', 'H'):
        elem_size = 2
    elif data_symbol in ('i', 'f'):
        elem_size = 4
    elif data_symbol == 'd':
        elem_size = 8
    padding = line_step - width * n_channel * elem_size

    # Format memory data to load into the image.
    image_data = []
    if n_channel == 1:
        mode = 'L'
        fmt = '%d%s%dx' % (width, data_symbol, padding)
        for line in chunker(memory_data, line_step):
            image_data.extend(struct.unpack(fmt, line))
    elif n_channel == 3:
        mode = 'RGB'
        fmt = '%d%s%dx' % (width * 3, data_symbol, padding)
        for line in chunker(memory_data, line_step):
            image_data.extend(struct.unpack(fmt, line))
    else:
        lldb.write('Only 1 or 3 channels supported\n', lldb.STDERR)
        return

    # Fit the opencv elemente data in the PIL element data
    if data_symbol == 'b':
        image_data = [i+128 for i in image_data]
    elif data_symbol == 'H':
        image_data = [i>>8 for i in image_data]
    elif data_symbol == 'h':
        image_data = [(i+32768)>>8 for i in image_data]
    elif data_symbol == 'i':
        image_data = [(i+2147483648)>>24 for i in image_data]
    elif data_symbol in ('f','d'):
        # A float image is discretized in 256 bins for display.
        max_image_data = max(image_data)
        min_image_data = min(image_data)
        img_range = max_image_data - min_image_data
        if img_range > 0:
            image_data = [int(255 * (i - min_image_data) / img_range) \
                            for i in image_data]
        else:
            image_data = [0 for i in image_data]


    if n_channel == 3:
        # OpenCV stores the channels in BGR mode. Convert to RGB while packing.
        image_data = zip(*[image_data[i::3] for i in [2, 1, 0]])

    # Make the Image
    img = Image.new(mode, (width, height))
    img.putdata(image_data)
    return img;

def create_imshow_options():
    usage = 'usage: %prog [options] img_variable'
    description='''This command allows you to visualize a cv::Mat object using the native image displaying application'''
    parser = optparse.OptionParser(description=description, prog='cv_imshow', usage=usage)
    parser.add_option('-w', '--window-name', dest='window_name', type='string', default='img',
                      help='The window name for displaying the image')
    return parser

def cv_imshow(debugger, command, result, internal_dict):
    command_args = shlex.split(command)
    parser = create_imshow_options()
    try:
        (options, args) = parser.parse_args(command_args)
        if len(args) < 1:
            parser.error("Please input the variable to display");
    except:
        return

    target = debugger.GetSelectedTarget()
    process = target.GetProcess()
    thread = process.GetSelectedThread()
    frame = thread.GetSelectedFrame()
    cv_img = frame.FindVariable(args[0])
    if not cv_img:
        result.SetError('The image is not found.')
        return
    window_name = options.window_name
    tmp_dir = os.path.join(os.getenv('TMPDIR', '/tmp'), 'lldb_cv_imshow')

    img_info = get_cvmat_info(cv_img)
    try:
        pil_image = create_pil_image(process, *img_info)
        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)
        filename = os.path.join(tmp_dir, '%s.png' % window_name)
        pil_image.save(filename)
        subprocess.call(["open", filename])
    except IOError:
        result.SetError('Unable to show the image')

def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand('command script add -f cv_imshow.cv_imshow cv_imshow')

