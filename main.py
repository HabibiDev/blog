import os
import datetime
import pymongo
import urllib.parse as urlparse
from werkzeug.wrappers import Request, Response
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import HTTPException, NotFound
from werkzeug.wsgi import SharedDataMiddleware
from werkzeug.utils import redirect
from jinja2 import Environment, FileSystemLoader
from bson.objectid import ObjectId


def is_valid_url(url):
    parts = urlparse.urlparse(url)
    return parts.scheme in ('http', 'https')


def get_hostname(url):
    return urlparse.urlparse(url).netloc


class Blogger(object):

    def __init__(self, config):
        self.mongo = pymongo.MongoClient(config['mongo_host'], config[
                                         'mongo_port'])['blog'].myposts
        template_path = os.path.join(os.path.dirname(__file__), 'templates')
        self.jinja_env = Environment(loader=FileSystemLoader(template_path),
                                     autoescape=True)
        self.jinja_env.filters['hostname'] = get_hostname
        self.url_map = Map([
            Rule('/', endpoint='list_of_posts'),
            Rule('/add_post', endpoint='new_post'),
            Rule('/<_id>', endpoint='post_detail')

        ])

    def new_post(self, request):
        error = None
        if request.method == 'POST':
            title = request.form.get('title')
            description = request.form.get('description')
            short_description = description[:120]
            data = datetime.datetime.now()
            if title == None:
                error = 'Please input title'
            elif description == None:
                error = 'Please input description'
            else:
                post = {'title': title,
                        'description': description,
                        'short_description': short_description,
                        'date_publish': data}
                self.mongo.insert_one(post)
                return redirect('/')
        return self.render_template('new_post.html', error=error)

    def list_of_posts(self, request):
        content = []
        for post in self.mongo.find():
            content.append(post)
        return self.render_template('list_of_posts.html', posts=content)

    def post_detail(self, request, _id):
        post_id = self.mongo.find_one({'_id': ObjectId(_id)})
        if post_id is None:
            raise NotFound()
        return self.render_template('post_details.html', post=post_id)

    def error_404(self):
        response = self.render_template('404.html')
        response.status_code = 404
        return response

    def render_template(self, template_name, **context):
        t = self.jinja_env.get_template(template_name)
        return Response(t.render(context), mimetype='text/html')

    def dispatch_request(self, request):
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            return getattr(self, endpoint)(request, **values)
        except NotFound as e:
            return self.error_404()
        except HTTPException as e:
            return e

    def wsgi_app(self, environ, start_response):
        request = Request(environ)
        response = self.dispatch_request(request)
        return response(environ, start_response)

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)


def create_app(mongo_host='localhost', mongo_port=27017, with_static=True):
    app = Blogger({
        'mongo_host':       mongo_host,
        'mongo_port':       mongo_port
    })
    if with_static:
        app.wsgi_app = SharedDataMiddleware(app.wsgi_app, {
            '/static':  os.path.join(os.path.dirname(__file__), 'static')
        })
    return app


if __name__ == '__main__':
    from werkzeug.serving import run_simple
    app = create_app()
    run_simple('127.0.0.1', 5000, app, use_debugger=True, use_reloader=True)
