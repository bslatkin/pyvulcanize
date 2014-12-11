This is still a work in progress. It is not functional.

#### TODO:

- Output a vulcanized HTML file
- Output a concatenated JavaScript file
- Generate source maps for the JavaScript files
- WSGI component for serving vulcanized files and original sources

### To test the example

#### 1. The JavaScript stuff

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

#### 2. The Python stuff

Now go back to the main project directory. Make sure you have `virtualenv` installed for Python 2.7:

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

#### Reproducing the existing output

In the example directory use the vulcanize tool (`npm install vulcanize`) to generate the expected output. Note you need to use the "content security policy" flag to have it generate an external JS file.

```
 ./node_modules/vulcanize/bin/vulcanize --csp -o official_test.html ./index.html
```
