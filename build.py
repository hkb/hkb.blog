import os, re, sys
import string, random
import datetime

import liquid, json, yaml
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import markdown
from markdown.extensions.toc import TocExtension
from markdown.inlinepatterns import SimpleTagPattern, InlineProcessor
from markdown.extensions import Extension
import xml.etree.ElementTree as etree


class ButtonInlineProcessor(InlineProcessor):
    def handleMatch(self, m, data):
        text = m.group(1)
        href = m.group(2)
        el = etree.fromstring(f'<div class="p-4 text-center"><a href="{href}" class="button group text-lg">{text}<span class="relative transition duration-100 group-hover:translate-x-1"><svg viewBox="0 0 448 512"><path d="M264.6 70.63l176 168c4.75 4.531 7.438 10.81 7.438 17.38s-2.688 12.84-7.438 17.38l-176 168c-9.594 9.125-24.78 8.781-33.94-.8125c-9.156-9.5-8.812-24.75 .8125-33.94l132.7-126.6H24.01c-13.25 0-24.01-10.76-24.01-24.01s10.76-23.99 24.01-23.99h340.1l-132.7-126.6C221.8 96.23 221.5 80.98 230.6 71.45C239.8 61.85 254.1 61.51 264.6 70.63z"></path></svg></span></a></div>')
        return el, m.start(0), m.end(0)

class ButtonExtension(Extension):
    def extendMarkdown(self, md):
        BUTTON_PATTERN = r'\[\[(.*?)\]\]\((.*?)\)'  # like [[Button Text]](https://example.com)
        md.inlinePatterns.register(ButtonInlineProcessor(BUTTON_PATTERN, md), 'button', 175)


from css_html_js_minify import html_minify, js_minify, css_minify

from PIL import Image




INPUT = 'src'
OUTPUT = '.site'
v = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(4))

IMAGE_FORMATS = ('webp', 'png', 'jpeg')
IMAGE_WIDTHS = (360, 800, 1200, 2400)

SINGLE_PAGE = sys.argv[1] if len(sys.argv) > 1 else None


def main():
    with open('CNAME', 'r') as src, open(f'{OUTPUT}/CNAME', 'w') as dst: dst.write(src.read())
    with open('.nojekyll', 'r') as src, open(f'{OUTPUT}/.nojekyll', 'w') as dst: dst.write(src.read())

    src_files = get_all_file_paths(INPUT)

    pages = []

    for file in src_files:
        ext = file.split('.')[-1]

        if ext in ('png', 'jpg', 'jpeg', 'webp') and not SINGLE_PAGE:
            copy_image(file)
        
        elif ext == 'svg' and not SINGLE_PAGE:
            copy_svg(file)

        elif ext == 'js' and not SINGLE_PAGE:
            copy_js(file)

        elif ext == 'css' and not SINGLE_PAGE:
            copy_css(file)
        
        elif ext in ('html', 'md'):
            print('📄', file)

            headers, content = split_headers_and_content(read(file))

            if ext == 'md':
                content = markdown.markdown(content, extensions=[
                    TocExtension(toc_depth='2-4'),
                    MarkdownHighlightExtension(),
                    ButtonExtension(),
                    'admonition',
                    'tables',
                    'fenced_code'
                ])

            page = headers
            page['content'] = content
            page['url'] = input_path_to_url(file)
            page['file'] = file
            page['tld'] = page['url'].split('/')[1]

            if 'image' not in page:
                pass#page['image'] = generate_open_graph_image(page)

            pages.append(page)

    # render pages
    template = read('index.html')
    environment = liquid.Environment(loader=liquid.loaders.FileSystemLoader('components/'))
    
    environment.add_filter('json', json.loads)
    environment.add_filter('yaml', lambda s: yaml.load(s, Loader=Loader))
    environment.add_filter('get_tag_list', get_tag_list)
    environment.add_filter('format_tags', format_tags)
    environment.add_filter('has', lambda ps, key: list(filter(lambda p: bool(p.get(key)), ps)))
    environment.add_filter('has_tag', lambda ps, tag: list(filter(lambda p: tag in p.get('tags', ''), ps)))
    environment.add_filter('reading_time', lambda s: max(int(count_real_words(s) / 200), 1))
    environment.add_filter('url_starts_with', lambda ps, prefix: list(filter(lambda p: p['url'].startswith(prefix), ps)))
    
    template = environment.from_string(template)
    for page in pages:
        if SINGLE_PAGE and SINGLE_PAGE not in page['file']:
            print('⏭️', page['url'])
            continue
        print('👷', page['url'])

        page = dict(page)
        content = page.pop('content')
        content = environment.from_string(content).render(pages=pages, **page)
        rendered = template.render(content=content, pages=pages, **page)

        write(input_path_to_output_path(page['file'].replace('.md', '.html')), html_minify(imgs_to_pictures(rendered)))
    # render sitemap.xml
    print('🗺️', 'sitemap.xml')
    write(OUTPUT + '/sitemap.xml', sitemap(pages))

    print('📰', 'feed.xml') 
    write(OUTPUT + '/feed.xml', feed(pages))
    
    print('🤖', 'robots.txt')
    write(OUTPUT + '/robots.txt', 'User-agent: *\nAllow: /\nDisallow: /thank-you/\n\nSitemap: https://hkb.blog/sitemap.xml')



# make sitemap and feed
def sitemap(pages):
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']

    for page in pages:
        # skip indexing
        if page.get('index') == 'no' or page['url'].startswith('/thank-you/'):
            continue

        # add to sitemap
        sitemap.append('<url>')
        sitemap.append(f"<loc>https://hkb.blog{page['url']}</loc>")

        if 'created_at' in page or 'updated_at' in page:
            sitemap.append(f"<lastmod>{page.get('updated_at') or page.get('created_at')}</lastmod>")

        sitemap.append('</url>')

    sitemap.append('</urlset>')

    return ''.join(sitemap)

def feed(pages):
    feed = ['<feed xmlns="http://www.w3.org/2005/Atom">']
    feed.append('<title>Update Mate Blog</title>')
    feed.append('<subtitle>We write about how to make work more joyful.</subtitle>')
    feed.append('<link href="https://hkb.blog/feed.xml" rel="self"/>')
    feed.append('<link href="https://hkb.blog/"/>')
    feed.append(f'<updated>{str(datetime.datetime.now())}</updated>')
    feed.append('<id>https://hkb.blog/</id>')

    for page in pages:
        # skip indexing
        if not page['url'].startswith('/blog/'):
            continue

        feed.append('<entry>')
        feed.append(f'<title>{page["title"]}</title>')
        feed.append(f'<summary>{page["description"]}</summary>')
        feed.append(f"<link href=\"https://hkb.blog{page['url']}\" />")
        
        if page.get('created_at'):
            feed.append(f'<published>{page["created_at"]}</published>')
        
        if page.get('updated_at'):
            feed.append(f'<updated>{page["updated_at"]}</updated>')
        
        feed.append('</entry>')

    feed.append('</feed>')

    return ''.join(feed)

# liquid filters
def get_tag_list(tags_string):
    return re.findall(r'\B#\w*[a-zA-Z]+[\w-]*', tags_string)

def format_tags(tags):
    if isinstance(tags, str):
        tags = get_tag_list(tags)

    tag_links = [f'<a href="/blog/tag/{tag[1:]}" class="clean inline-block m-1 px-3 py-0.5 rounded-full text-xs text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-700">{tag}</a>' for tag in tags]

    return ' '.join(tag_links)


# markdown extensions
class MarkdownHighlightExtension(Extension):
    """Adds MARK_RE extension to Markdown class."""
    
    def extendMarkdown(self, md, md_globals):
        """Modifies inline patterns."""
        mark_tag = SimpleTagPattern(r'(==)(.*?)(==)', 'mark')
        md.inlinePatterns.add('mark', mark_tag, '_begin')


# compilers
def copy_image(file):
    print('[COPY IMAGE]', file)
    outfile = input_path_to_output_path(file)

    if os.path.isfile(outfile):
        print('  Image already rendered - skipping...')
        return

    image = Image.open(file)

    # output 
    make_dirs(outfile)
    image.save(outfile)

    # make smaller files
    outfile_base, outfile_ext = outfile.rsplit('.', 1)
    orig_width, orig_height = image.size

    for width in sorted(IMAGE_WIDTHS, reverse=True):
        for format in IMAGE_FORMATS:
            if same_image_format(outfile_ext, format) or same_image_format(format, 'webp'):
                outfile_thumb = f'{outfile_base}_{width}.{format}'

                # only make copies in files own format or webp
                img = image

                if width < orig_width:
                    print('  ', outfile_thumb)
                    img = img.resize((width, int(orig_height * width/orig_width))) # only downscale

                img.save(outfile_thumb, format)

def copy_svg(file):
    print('[COPY SVG]', file)
    write(input_path_to_output_path(file), read(file))

def copy_js(file):
    print('[COPY JS]', file)
    write(input_path_to_output_path(file), js_minify(read(file)))

def copy_css(file):
    print('[COPY CSS]', file)
    write(input_path_to_output_path(file), css_minify(read(file)))



# helpers
def read(path):
    with open(path) as f:
        return f.read()

def write(path, content):
    make_dirs(path)

    with open(path, 'w') as f:
        f.write(content)

def make_dirs(path):
    dir_path = '/'.join(path.split('/')[:-1])
    os.makedirs(dir_path, exist_ok=True)

def get_all_file_paths(dir):
    return [os.path.join(r, file) for r, d, fs in os.walk(dir) for file in fs if file[0] != '.']

def input_path_to_output_path(input_path):
    return OUTPUT + input_path[len(INPUT):]

def input_path_to_url(input_path):
    return input_path[len(INPUT):].split('.')[0].replace('/index', '/')

def split_headers_and_content(text):
    if text[:3] != '---' and text.count('---') < 2:
        return {}, text

    raw_headers, content = text[3:].split('---', 1)

    headers = dict()
    for header in raw_headers.split('\n'):
        if ':' in header:
            key, value = header.split(':', 1)
            headers[key.strip()] = value.strip()

    return headers, content

def count_real_words(sentence):
    # Remove HTML tags
    sentence = re.sub(r'<[^>]+>', '', sentence)
    # Use regular expression to find words containing only letters a-z
    words = re.findall(r'\b[a-zA-Z]+\b', sentence)
    # Count the number of such words
    count = len(words)
    return count

def open_external_links_in_new_tab(html):
    return re.sub(r'<a\s+([^>]*)href="(http?[^"]+)"([^>]*)>', r'<a \1href="\2" target="_blank"\3>', html)

def imgs_to_pictures(html):
    for img in re.findall('<img.*?>', html):
        html = html.replace(img, img_to_picture(img))

    return html.replace('<p><figure', '<figure').replace('</figure></p>', '</figure>')

def generate_open_graph_image(page):
    og_url = f'/images/og/{page["file"].replace("src/", "").split(".")[0]}.jpg'
    og_location = f'{OUTPUT}{og_url}'

    from PIL import Image, ImageDraw, ImageFont
    img = Image.new('RGB', (1200, 630), color='white')
    
    # Initialize the drawing context
    draw = ImageDraw.Draw(img)
    
    # Load a font (using a system font)
    font = ImageFont.load_default()
    
    # Calculate text size and position
    text_width, text_height = draw.textsize(page['url'], font=font)
    text_x = (img.width - text_width) / 2
    text_y = (img.height - text_height) / 2
    
    # Draw text on the image
    draw.text((text_x, text_y), page['url'], fill='black', font=font)
    
    # Save the image
    make_dirs(og_location)
    print(og_location)
    img.save(og_location)
    
    return og_url

def img_to_picture(img):
    src = re.search(' src=["|\'](.*?)["|\']', img)[1]
    title = re.search(' title=["|\'](.*?)["|\']', img)
    title = title[1] if title else None

    if title:
        img = img.replace('<img', f'<img alt="{title}"')
    else:
        img = img.replace('<img', '<img alt=""')

    output = ['<figure>'] if title else []

    if '.' not in src:
        print('  [WARN] Could not optimize image: ', img)
        return img

    base, ext = src.rsplit('.', 1)

    if ext.lower() in ('png', 'jpg', 'jpeg', 'webp'):
        output.append('<picture>')

        for format in IMAGE_FORMATS:
            for width in sorted(IMAGE_WIDTHS, reverse=True):
                if same_image_format(ext, format) or same_image_format(format, 'webp'):
                    output.append(f'<source srcset="{base}_{width}.{format}, {base}_{next_width(width)}.{format} {round(next_width(width)/width, 1)}x" type="image/{format}" media="(min-width: {width}px)">')

        output.append(img.replace('<img', '<img loading="lazy"'))

        output.append('</picture>')
    
    else:
       output.append(img.replace('<img', '<img loading="lazy"'))
 
    if title:
        output.append(f'<figcaption>{title}</figcaption>')

    if title:
        output.append('</figure>')

    return ''.join(output)

def next_width(width):
    i = IMAGE_WIDTHS.index(width)

    if i+1 < len(IMAGE_WIDTHS):
        return IMAGE_WIDTHS[i+1]

    return IMAGE_WIDTHS[-1]

def same_image_format(a, b):
    if a == 'jpg':
        a = 'jpeg'
    else:
        a = a.lower()

    if b == 'jpg':
        b = 'jpeg'
    else:
        b = b.lower()

    return a == b

# run main on main
if __name__ == '__main__':
    main()