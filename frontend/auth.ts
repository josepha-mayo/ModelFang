import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    Credentials({
      name: "Credentials",
      credentials: {
        username: { label: "Username", type: "text" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        const validUsername = process.env.AUTH_USERNAME;
        const validPassword = process.env.AUTH_PASSWORD;
        
        if (!validUsername || !validPassword) {
           console.error("Missing AUTH_USERNAME or AUTH_PASSWORD env variables");
           return null;
        }

        if (
          credentials?.username === validUsername &&
          credentials?.password === validPassword
        ) {
          return {
            id: "1",
            name: validUsername,
            email: `${validUsername}@modelfang.local`,
          };
        }
        return null;
      },
    }),
  ],
  pages: {
    signIn: "/login",
  },
  trustHost: true,
});
