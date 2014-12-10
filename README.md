

#### To test the example

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
