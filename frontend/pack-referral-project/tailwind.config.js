/** @type {import('tailwindcss').Config} */

export default {
  content: ["./index.html", "./src/**/*.{jsx,css}", "./*.{html,js}"],
  theme: {
    extend: {
        colors: {
            ncstate : {

                wolfpackred: '#CC0000',
                wolfpackwhite: '#FFFFFF',
                wolfpackblack: '#000000',

            },
        },
    },
  },
  plugins: [],
}

