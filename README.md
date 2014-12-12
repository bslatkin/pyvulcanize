# pyvulcanize

*This is still a work in progress.*

A pure Python implementation of the [vulcanize tool](https://github.com/Polymer/vulcanize) that is part of the [Polymer project](https://www.polymer-project.org).

Why Python? Because my server is written in Python. I don't want to run node.js on the side during development just to regenerate vulcanized files on the fly. Oh-- and I want vulcanized files during development because the number of static resources I need to load for a large project gets excruciatingly slow to transfer, even on localhost (there are just too many HTTP requests to make).

## Using the tool

TODO: Write this

## Known limitations

Bugs:

- [Conditional binding syntax](https://www.polymer-project.org/docs/polymer/binding-types.html#conditional-attributes) doesn't work (i.e., `attribute?="value"``)
- `@import` in linked stylesheets won't be inlined
- `url()` or `@import` in linked stylesheets won't be adjusted for relative paths
- Document-level `<style>` tags aren't getting copied through

Missing features:

- Tests
- setup.py and pypi
- Output a concatenated JavaScript file
- Generate source maps for the JavaScript files

## Test the tool during development

Read this if you want to edit this code and contribute. Please send edits as pull requests.

### 1. Dependencies

This section makes me want to scream, but alas this is how it is.

Go into the `example` directory:

```
cd example
```

Have a copy of [`npm`](https://www.npmjs.com/) installed. On a Mac you can use [`brew`](http://brew.sh/) to do this:

```
brew install npm
```

Have the `npm` package [`bower`](http://bower.io/) installed:

```
npm install bower
```

That will create a directory called `node_modules` somewhere in your project directory. Reach into that directory and run the bower binary:

```
./node_modules/bower/bin/bower install
```

If that worked, you'll see a file named `bower_components/webcomponentsjs/webcomponents.js` in the `example` directory.

### 2. Using the JS tool

This is how you use the [official version of vulcanize](https://github.com/Polymer/vulcanize) to produce the desired output.

In the example directory use the vulcanize tool (`npm install vulcanize`) to generate the expected output. Note you need to use the "content security policy" flag to have it generate an external JS file.

```
 ./node_modules/vulcanize/bin/vulcanize --csp -o official_test.html ./index.html
```

### 3. Using the Python tool

Go to the main project directory. Make sure you have `virtualenv` installed for Python 2.7:

```
pip install virtualenv
```

Create a new virtual environment for the project in the project's root directory.

```
virtualenv .
```

Activate the virtual environment:

```
source bin/activate
```

Then install all of the requirements for the Python part of the project:

```
pip install -r ./requirements.txt
```

From the project root directory, you should be able to run the commandline tool with:

```
python -m vulcanize ./example/index.html -o ./example/test.html
```

To see if it worked, run a Python server locally:

```
python -m SimpleHTTPServer 8080 ./example
```

And then visit <http://localhost:8080/test.html>. If you see a big green square with JS on it, you're good.

## About

Written by [Brett Slatkin](http://www.onebigfluke.com)
